#############################################
 Configuration File ``.idf_build_apps.toml``
#############################################

There are many CLI options available for ``idf-build-apps``. While these options provide usage flexibility, they also make the CLI command too long and difficult to read. However, a configuration file allows defining all these options in a more readable and maintainable way.

***********************
 Config File Discovery
***********************

``idf-build-apps`` supports a few ways to specify the configuration file (in order of precedence):

-  specify via CLI argument ``--config-file <config file path>``
-  ``.idf_build_apps.toml`` in the current directory
-  ``.idf_build_apps.toml`` in the parent directories, until it reaches the root of the file system
-  ``pyproject.toml`` with ``[tool.idf-build-apps]`` section
-  ``pyproject.toml`` in the parent directories, until it reaches the root of the file system

*******
 Usage
*******

We recommend using the ``.idf_build_apps.toml`` file for non-Python projects and the ``pyproject.toml`` file for Python projects. When using the ``pyproject.toml`` file, define the configuration options in the ``[tool.idf-build-apps]`` section.

Here's a simple example of a configuration file:

.. tabs::

   .. group-tab::

      ``.idf_build_apps.toml``

      .. code:: toml

         paths = [
             "components",
             "examples",
         ]
         target = "esp32"
         recursive = true

         # config rules
         config = [
             "sdkconfig.*=",
             "=default",
         ]

   .. group-tab::

      ``pyproject.toml``

      .. code:: toml

         [tool.idf-build-apps]
         paths = [
             "components",
             "examples",
         ]
         target = "esp32"
         recursive = true

         # config rules
         config = [
             "sdkconfig.*=",
             "=default",
         ]

Running ``idf-build-apps build`` with the above configuration is equivalent to the following CLI command:

.. code:: shell

   idf-build-app build \
     --paths components examples \
     --target esp32 \
     --recursive \
     --config-rules "sdkconfig.*=" "=default" \
     --build-dir "build_@t_@w"

`TOML <https://toml.io/en/>`__ supports native data types. In order to get the config name and type of the corresponding CLI option, you may refer to the help messages by using ``idf-build-apps find -h`` or ``idf-build-apps build -h``.

For instance, the ``--paths`` CLI option help message shows:

.. code:: text

   -p PATHS [PATHS ...], --paths PATHS [PATHS ...]
                        One or more paths to look for apps.
                         - default: None
                         - config name: paths
                         - config type: list[str]

This indicates that in the configuration file, you should specify it with the name ``paths``, and the type should be a “list of strings”.

.. code:: toml

   paths = [
       "foo",
       "bar",
   ]

******************************
 Expand Environment Variables
******************************

All configuration options support environment variables. You can use environment variables in the configuration file by using the syntax ``${VAR_NAME}`` or ``$VAR_NAME``. Undeclared environment variables will be replaced with an empty string. For example:

.. code:: toml

   collect_app_info_filename = "app_info_${CI_JOB_NAME_SLUG}"

when the environment variable ``CI_JOB_NAME_SLUG`` is set to ``my_job``, the ``collect_app_info_filename`` will be expanded to ``app_info_my_job``. When the environment variable is not set, the value will be ``app_info_``.

*************************
 CLI Argument Precedence
*************************

CLI arguments take precedence over the configuration file. This helps to override the configuration file settings when required.

For example, if the configuration file has the following content:

.. tabs::

   .. group-tab::

      ``.idf_build_apps.toml``

      .. code:: toml

         target = "esp32"
         config_rules = [
             "sdkconfig.*=",
             "=default",
         ]

   .. group-tab::

      ``pyproject.toml``

      .. code:: toml

         [tool.idf-build-apps]
         target = "esp32"
         config_rules = [
             "sdkconfig.*=",
             "=default",
         ]

Override String Configuration
=============================

To override the ``str`` type configuration, (e.g., ``target``), you can pass the CLI argument directly:

.. code:: shell

   idf-build-apps build --target esp32s2

Override List Configuration
===========================

To override the ``list[str]`` type configuration, (e.g., ``config_rules``), you can override it by passing the CLI argument. For example:

.. code:: shell

   idf-build-apps build --config-rules "foo=bar"

Or you can unset the configuration by passing an empty string:

.. code:: shell

   idf-build-apps build --config-rules ""

Override Boolean Configuration
==============================

Not supported yet.
