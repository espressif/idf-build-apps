# PYTHON_ARGCOMPLETE_OK

# SPDX-FileCopyrightText: 2022-2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import logging
import os
import sys
import textwrap
import typing as t
from dataclasses import asdict

import argcomplete
from pydantic import (
    Field,
    create_model,
)

from idf_build_apps.args import BuildArguments, DumpManifestShaArguments, FindArguments, add_arguments_to_parser

from .app import (
    App,
    AppDeserializer,
    CMakeApp,
    MakeApp,
)
from .autocompletions import activate_completions
from .constants import ALL_TARGETS, BuildStatus, completion_instructions
from .finder import (
    _find_apps,
)
from .junit import (
    TestCase,
    TestReport,
    TestSuite,
)
from .manifest.manifest import (
    Manifest,
)
from .utils import (
    AutocompleteActivationError,
    InvalidCommand,
    drop_none_kwargs,
    get_parallel_start_stop,
    to_list,
)

LOGGER = logging.getLogger(__name__)


def find_apps(
    paths: t.Union[t.List[str], str, None] = None,
    target: t.Optional[str] = None,
    *,
    find_arguments: t.Optional[FindArguments] = None,
    **kwargs,
) -> t.List[App]:
    """
    Find apps in the given paths for the specified target. For all kwargs, please refer to `FindArguments`

    :return: list of found apps
    """
    if find_arguments is None:
        find_arguments = FindArguments(
            paths=to_list(paths),  # type: ignore
            target=target,  # type: ignore
            **kwargs,
        )

    app_cls: t.Type[App]
    if isinstance(find_arguments.build_system, str):
        # backwards compatible
        if find_arguments.build_system == 'cmake':
            app_cls = CMakeApp
        elif find_arguments.build_system == 'make':
            app_cls = MakeApp
        else:
            raise ValueError('Only Support "make" and "cmake"')
    else:
        app_cls = find_arguments.build_system

    apps = []
    if find_arguments.target == 'all':
        targets = ALL_TARGETS
    else:
        targets = [find_arguments.target]

    for _t in targets:
        for _p in find_arguments.paths:
            apps.extend(
                _find_apps(
                    _p,
                    _t,
                    app_cls=app_cls,
                    args=find_arguments,
                )
            )

    LOGGER.info(f'Found {len(apps)} apps in total')

    return sorted(apps)


def build_apps(
    apps: t.Union[t.List[App], App, None] = None, *, build_arguments: t.Optional[BuildArguments] = None, **kwargs
) -> int:
    """
    Build all the specified apps. For all kwargs, please refer to `BuildArguments`

    :return: exit code
    """
    apps = to_list(apps)
    if build_arguments is None:
        build_arguments = BuildArguments(
            **kwargs,
        )

    if apps is None:
        apps = find_apps(find_arguments=FindArguments.from_dict(asdict(build_arguments)))

    test_suite = TestSuite('build_apps')

    start, stop = get_parallel_start_stop(len(apps), build_arguments.parallel_count, build_arguments.parallel_index)
    LOGGER.info('Total %s apps. running build for app %s-%s', len(apps), start, stop)

    # cleanup collect files if exists at this early-stage
    for f in (build_arguments.collect_app_info, build_arguments.collect_size_info, build_arguments.junitxml):
        if f and os.path.isfile(f):
            os.remove(f)
            LOGGER.debug('Remove existing collect file %s', f)

    exit_code = 0
    for i, app in enumerate(apps):
        index = i + 1  # we use 1-based
        if index < start or index > stop:
            continue

        # attrs
        app.dry_run = build_arguments.dry_run
        app.index = index
        app.verbose = build_arguments.build_verbose
        app.copy_sdkconfig = build_arguments.copy_sdkconfig

        LOGGER.info('(%s/%s) Building app: %s', index, len(apps), app)

        app.build(
            manifest_rootpath=build_arguments.manifest_rootpath,
            modified_components=build_arguments.modified_components,
            modified_files=build_arguments.modified_files,
            check_app_dependencies=build_arguments.dependency_driven_build_enabled,
        )
        test_suite.add_test_case(TestCase.from_app(app))

        if app.build_comment:
            LOGGER.info('%s (%s)', app.build_status.value, app.build_comment)
        else:
            LOGGER.info('%s', app.build_status.value)

        if build_arguments.collect_app_info:
            with open(build_arguments.collect_app_info, 'a') as fw:
                fw.write(app.to_json() + '\n')
            LOGGER.debug('Recorded app info in %s', build_arguments.collect_app_info)

        if app.build_status == BuildStatus.FAILED:
            if not build_arguments.keep_going:
                return 1
            else:
                exit_code = 1
        elif app.build_status == BuildStatus.SUCCESS:
            if build_arguments.collect_size_info and app.size_json_path:
                if os.path.isfile(app.size_json_path):
                    with open(build_arguments.collect_size_info, 'a') as fw:
                        fw.write(
                            json.dumps(
                                {
                                    'app_name': app.name,
                                    'config_name': app.config_name,
                                    'target': app.target,
                                    'path': app.size_json_path,
                                }
                            )
                            + '\n'
                        )
                    LOGGER.debug('Recorded size info file path in %s', build_arguments.collect_size_info)

        LOGGER.info('')  # add one empty line for separating different builds

    if build_arguments.junitxml:
        TestReport([test_suite], build_arguments.junitxml).create_test_report()
        LOGGER.info('Generated junit report for build apps: %s', build_arguments.junitxml)

    return exit_code


class IdfBuildAppsCliFormatter(argparse.HelpFormatter):
    LINE_SEP = '$LINE_SEP$'

    def _split_lines(self, text, width):
        parts = text.split(self.LINE_SEP)

        text = self._whitespace_matcher.sub(' ', parts[0]).strip()
        return textwrap.wrap(text, width) + parts[1:]

    def _get_help_string(self, action):
        """
        Add the default value to the option help message.

        ArgumentDefaultsHelpFormatter and BooleanOptionalAction when it isn't
        already present. This code will do that, detecting corner cases to
        prevent duplicates or cases where it wouldn't make sense to the end
        user.
        """
        _help = action.help
        if _help is None:
            _help = ''

        if action.dest == 'config_file':
            return _help

        if action.default is not argparse.SUPPRESS:
            if action.default is None:
                default_type = str
            else:
                default_type = type(action.default)

            if action.nargs in [argparse.ZERO_OR_MORE, argparse.ONE_OR_MORE]:
                _type = f'list[{default_type.__name__}]'
            else:
                _type = default_type.__name__

            defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
            if action.option_strings or action.nargs in defaulting_nargs:
                _help += f'{self.LINE_SEP} - default: %(default)s'

            _help += f'{self.LINE_SEP} - config name: {action.dest}'
            _help += f'{self.LINE_SEP} - config type: {_type}'

        return _help


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Tools for building ESP-IDF related apps. '
        'Some CLI options can be expanded by the following placeholders, like "--work-dir", "--build-dir", etc.:\n'
        '- @t: would be replaced by the target chip type\n'
        '- @w: would be replaced by the wildcard, usually the sdkconfig\n'
        '- @n: would be replaced by the app name\n'
        '- @f: would be replaced by the escaped app path (replaced "/" to "_")\n'
        '- @v: Would be replaced by the ESP-IDF version like `5_3_0`\n'
        '- @i: would be replaced by the build index (only available in `build` command)\n'
        '- @p: would be replaced by the parallel index (only available in `build` command)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    actions = parser.add_subparsers(dest='action', required=True)

    ########
    # Find #
    ########
    find_parser = actions.add_parser(
        'find',
        help='Find the buildable applications. Run `idf-build-apps find --help` for more information on a command.',
        description='Find the buildable applications in the given path or paths for specified chips. '
        '`--path` and `--target` options must be provided. '
        'By default, print the found apps in stdout. '
        'To find apps for all chips use the `--target` option with the `all` argument.',
        formatter_class=IdfBuildAppsCliFormatter,
    )
    add_arguments_to_parser(FindArguments, find_parser)

    #########
    # Build #
    #########
    build_parser = actions.add_parser(
        'build',
        help='Build the found applications. Run `idf-build-apps build --help` for more information on a command.',
        description='Build the application in the given path or paths for specified chips. '
        '`--path` and `--target` options must be provided.',
        formatter_class=IdfBuildAppsCliFormatter,
    )
    add_arguments_to_parser(BuildArguments, build_parser)

    ###############
    # Completions #
    ###############
    completions_parser = actions.add_parser(
        'completions',
        help='Add the autocompletion activation script to the shell rc file. '
        'Run `idf-build-apps completions --help` for more information on a command.',
        description='Without `--activate` option print instructions for manual activation. '
        'With the `--activate` option, add the autocompletion activation script to the shell rc file '
        'for bash, zsh, or fish. Other shells are not supported.'
        'The `--shell` option is used only with the `--activate` option, '
        'if provided, add the autocompletion activation script to the given shell; '
        'without this argument, will detect shell type automatically. '
        'May need to restart or re-login for the autocompletion to start working',
        formatter_class=IdfBuildAppsCliFormatter,
    )
    completions_parser.add_argument(
        '-a', '--activate', action='store_true', help='Activate autocompletion automatically and permanently. '
    )
    completions_parser.add_argument(
        '-s',
        '--shell',
        choices=['bash', 'zsh', 'fish'],
        help='Specify the shell type for the autocomplete activation script.',
    )

    ############################
    # Dump Manifest SHA Values #
    ############################
    dump_manifest_parser = actions.add_parser(
        'dump-manifest-sha',
        help='Dump the manifest files SHA values. '
        'This could be useful in CI to check if the manifest files are changed.',
    )
    add_arguments_to_parser(DumpManifestShaArguments, dump_manifest_parser)

    return parser


def handle_completions(args: argparse.Namespace) -> None:
    if args.activate:
        if not args.shell:
            args.shell = 'auto'
        activate_completions(args.shell)
    elif not args.activate and args.shell:
        raise AutocompleteActivationError('The --shell option can only be used with the --activate option.')
    else:
        print(completion_instructions)


def main():
    parser = get_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.action == 'completions':
        handle_completions(args)
        sys.exit(0)

    if args.action == 'dump-manifest-sha':
        arguments = DumpManifestShaArguments.from_dict(drop_none_kwargs(vars(args)))
        Manifest.from_files(arguments.manifest_files).dump_sha_values(arguments.output)
        sys.exit(0)

    if args.action == 'find':
        arguments = FindArguments.from_dict(drop_none_kwargs(vars(args)))
    else:
        arguments = BuildArguments.from_dict(drop_none_kwargs(vars(args)))

    # real call starts here
    # build also needs to find first
    apps = find_apps(args.paths, args.target, find_arguments=arguments)
    if isinstance(arguments, FindArguments):  # find only
        if arguments.output:
            os.makedirs(os.path.dirname(os.path.realpath(arguments.output)), exist_ok=True)
            with open(arguments.output, 'w') as fw:
                if arguments.output_format == 'raw':
                    for app in apps:
                        fw.write(app.to_json() + '\n')
                elif arguments.output_format == 'json':
                    fw.write(json.dumps([app.model_dump() for app in apps], indent=2))
                else:
                    raise InvalidCommand(f'Output format {arguments.output_format} is not supported.')
        else:
            for app in apps:
                print(app)

        sys.exit(0)

    # build
    if arguments.no_preserve:
        for app in apps:
            app.preserve = False

    ret_code = build_apps(apps, build_arguments=arguments)

    built_apps = [app for app in apps if app.build_status == BuildStatus.SUCCESS]
    if built_apps:
        print('Successfully built the following apps:')
        for app in built_apps:
            print(f'  {app}')

    skipped_apps = [app for app in apps if app.build_status == BuildStatus.SKIPPED]
    if skipped_apps:
        print('Skipped building the following apps:')
        for app in skipped_apps:
            print(f'  {app}')

    failed_apps = [app for app in apps if app.build_status == BuildStatus.FAILED]
    if failed_apps:
        print('Failed building the following apps:')
        for app in failed_apps:
            print(f'  {app}')

    sys.exit(ret_code)


def json_to_app(json_str: str, extra_classes: t.Optional[t.List[t.Type[App]]] = None) -> App:
    """
    Deserialize json string to App object

    .. note::

        You can pass extra_cls to support custom App class. A custom App class must be a subclass of App, and have a
        different value of `build_system`. For example, a custom CMake app

        .. code:: python

           class CustomApp(CMakeApp):
               build_system: Literal['custom_cmake'] = 'custom_cmake'

        Then you can pass the :class:`CustomApp` class to the :attr:`extra_cls` argument

        .. code:: python

           json_str = CustomApp('.', 'esp32').to_json()
           json_to_app(json_str, extra_classes=[CustomApp])

    :param json_str: json string
    :param extra_classes: extra App class
    :return: App object
    """
    types = [App, CMakeApp, MakeApp]
    if extra_classes:
        types.extend(extra_classes)

    custom_deserializer = create_model(
        '_CustomDeserializer',
        app=(t.Union[tuple(types)], Field(discriminator='build_system')),
        __base__=AppDeserializer,
    )

    return custom_deserializer.from_json(json_str)
