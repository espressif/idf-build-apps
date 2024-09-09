###############
 Build Command
###############

.. note::

   If you are unfamiliar with the the find command yet, please read the :doc:`find` first.

This page explains the process of build apps, and how to use the ``idf-build-apps build`` command to build apps in the projects.

.. note::

   For detailed list of arguments, please refer to the :class:`~idf_build_apps.args.FindArguments` reference.

*************************
 Basic ``build`` Command
*************************

.. code:: shell

   idf-build-apps build

*****************************
 ``build`` With Placeholders
*****************************

Besides of the :ref:`placeholders supported in find command <find-placeholders>`, the build command also supports the following placeholders:

-  ``@i``: Would be replaced by the build index.
-  ``@p``: Would be replaced by the parallel build index.

*******************************
 ``build`` With Warnings Check
*******************************

You may use `--check-warnings` to enable this check. If any warning is captured while the building process, the exit code would turn to a non-zero value. Besides, `idf-build-apps` provides CLI options `--ignore-warnings-str` and `--ignore-warnings-file` to let you bypass some false alarms.

***************************
 ``build`` With Debug Mode
***************************

It's useful to call `--dry-run` with verbose mode `-vv` to know the whole build process in detail before the build actually happens. For example:

.. code:: shell

   idf-build-apps build -p . --recursive --target esp32 --dry-run -vv --config "sdkconfig.ci.*="

The output would be:

.. code:: text

   2024-08-12 15:48:01    DEBUG Looking for CMakeApp apps in . recursively with target esp32
   2024-08-12 15:48:01    DEBUG Entering .
   2024-08-12 15:48:01    DEBUG Skipping. . is not an app
   2024-08-12 15:48:01    DEBUG Entering ./test-1
   2024-08-12 15:48:01    DEBUG sdkconfig file sdkconfig.defaults not found, checking under app_dir...
   2024-08-12 15:48:01    DEBUG Use sdkconfig file ./test-1/sdkconfig.defaults
   2024-08-12 15:48:01    DEBUG Use sdkconfig file /tmp/test/examples/test-1/sdkconfig.ci.bar
   2024-08-12 15:48:01    DEBUG Found app: (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.bar, build in ./test-1/build
   2024-08-12 15:48:01    DEBUG
   2024-08-12 15:48:01    DEBUG sdkconfig file sdkconfig.defaults not found, checking under app_dir...
   2024-08-12 15:48:01    DEBUG Use sdkconfig file ./test-1/sdkconfig.defaults
   2024-08-12 15:48:01    DEBUG Use sdkconfig file /tmp/test/examples/test-1/sdkconfig.ci.foo
   2024-08-12 15:48:01    DEBUG Found app: (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.foo, build in ./test-1/build
   2024-08-12 15:48:01    DEBUG
   2024-08-12 15:48:01    DEBUG => Stop iteration sub dirs of ./test-1 since it has apps
   2024-08-12 15:48:01    DEBUG Entering ./test-2
   2024-08-12 15:48:01    DEBUG sdkconfig file sdkconfig.defaults not found, checking under app_dir...
   2024-08-12 15:48:01    DEBUG sdkconfig file ./test-2/sdkconfig.defaults not found, skipping...
   2024-08-12 15:48:01    DEBUG Found app: (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build
   2024-08-12 15:48:01    DEBUG
   2024-08-12 15:48:01    DEBUG => Stop iteration sub dirs of ./test-2 since it has apps
   2024-08-12 15:48:01     INFO Found 3 apps in total
   2024-08-12 15:48:01     INFO Total 3 apps. running build for app 1-3
   2024-08-12 15:48:01     INFO (1/3) Building app: (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.bar, build in ./test-1/build
   2024-08-12 15:48:01     INFO [   Dry Run] Writing build log to ./test-1/build/.temp.build.-4727026790408965348.log
   2024-08-12 15:48:01     INFO skipped (dry run)
   2024-08-12 15:48:01     INFO
   2024-08-12 15:48:01     INFO (2/3) Building app: (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.foo, build in ./test-1/build
   2024-08-12 15:48:01     INFO [   Dry Run] Writing build log to ./test-1/build/.temp.build.4508471977171905517.log
   2024-08-12 15:48:01     INFO skipped (dry run)
   2024-08-12 15:48:01     INFO
   2024-08-12 15:48:01     INFO (3/3) Building app: (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build
   2024-08-12 15:48:01     INFO [   Dry Run] Writing build log to ./test-2/build/.temp.build.4188038822526638365.log
   2024-08-12 15:48:01     INFO skipped (dry run)
   2024-08-12 15:48:01     INFO
   Skipped building the following apps:
     (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.bar, build in ./test-1/build, skipped in 0.000635s: dry run
     (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.foo, build in ./test-1/build, skipped in 0.000309s: dry run
     (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build, skipped in 0.000265s: dry run
