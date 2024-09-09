##############
 Find Command
##############

.. note::

   If you are unfamiliar with the concept of sdkconfig files and config rules yet, please read the :doc:`config_rules` first.

This page explains the process of find apps, and how to use the ``idf-build-apps find`` command to search for apps in the project.

All examples are based on the following demo projects, with the folder structure:

.. code:: text

   /tmp/test/examples
   ├── test-1
   │   ├── CMakeLists.txt
   │   ├── main
   │   │   ├── CMakeLists.txt
   │   │   └── test-1.c
   │   ├── sdkconfig.ci.bar
   │   ├── sdkconfig.ci.foo
   │   ├── sdkconfig.defaults
   │   └── sdkconfig.defaults.esp32
   └── test-2
       ├── CMakeLists.txt
       └── main
           ├── CMakeLists.txt
           └── test-2.c

.. note::

   For detailed list of arguments, please refer to the :class:`~idf_build_apps.args.FindArguments` reference.

************************
 Basic ``find`` Command
************************

The basic command to find all the buildable apps under ``/tmp/test/examples`` recursively with target ``esp32`` is:

.. code:: shell

   cd /tmp/test/examples
   idf-build-apps find --path . --target esp32 --recursive

The output would be:

.. code:: shell

   (cmake) App ./test-1, target esp32, sdkconfig (default), build in ./test-1/build
   (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build

The default value of ``--path`` is the current directory, so the ``--path .`` can be omitted.

.. note::

   You may check the default values by running ``idf-build-apps find --help`` or check the :doc:`../references/cli`.

****************************
 ``find`` With Config Rules
****************************

To build one project with different configurations, you can use the :ref:`config-rules` to define the build configurations. The ``find`` command will build the project with all the matched configurations.

For example,

.. code:: shell

   idf-build-apps find -p test-1 --target esp32 --config "sdkconfig.ci.*="

The output would be:

.. code:: text

   (cmake) App test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.bar, build in test-1/build
   (cmake) App test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.foo, build in test-1/build

You may also use :ref:`config-rules` for multiple values:

.. code:: shell

   idf-build-apps find -p test-1 --target esp32 --config "sdkconfig.ci.*=" "sdkconfig.defaults=default"

The output would be:

.. code:: text

   (cmake) App test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.bar, build in test-1/build
   (cmake) App test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.foo, build in test-1/build
   (cmake) App test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.defaults, build in test-1/build

.. _find-placeholders:

****************************
 ``find`` With Placeholders
****************************

As you may notice in the earlier examples, ``idf-build-apps`` by default builds projects in-place, within the project directory, and generates the binaries under ``build`` directory (which is the default build directory for ESP-IDF projects). This makes it difficult to build all applications at the same time and keep the build artifacts separate in CI/CD pipelines.

``idf-build-apps`` supports placeholders to specify the build directory. The placeholders are replaced with the actual values during the call. The supported placeholders are:

-  ``@t``: Would be replaced by the target chip type.
-  ``@w``: Would be replaced by the wildcard if exists, otherwise would be replaced by the config name.
-  ``@n``: Would be replaced by the project name.
-  ``@f``: Would be replaced by the escaped project path (replaced "/" to "_").
-  ``@v``: Would be replaced by the ESP-IDF version like ``5_3_0``.

For example,

.. code:: shell

   idf-build-apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*=" --build-dir build_@t_@w

The output would be:

.. code:: text

   (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.bar, build in ./test-1/build_esp32_bar
   (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.foo, build in ./test-1/build_esp32_foo
   (cmake) App ./test-2, target esp32, sdkconfig (default), build in ./test-2/build_esp32

Another example to build these apps in a temporary directory:

.. code:: shell

   idf-build-apps find -p . --recursive --target esp32 --config "sdkconfig.ci.*=" --build-dir /tmp/build_@n_@t_@w

The output would be:

.. code:: text

   (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.bar, build in /tmp/build_test-1_esp32_bar
   (cmake) App ./test-1, target esp32, sdkconfig /tmp/test/examples/test-1/sdkconfig.ci.foo, build in /tmp/build_test-1_esp32_foo
   (cmake) App ./test-2, target esp32, sdkconfig (default), build in /tmp/build_test-2_esp32

******************
 Output to a File
******************

For `find` command, we support both "raw" format, and "json" format. The default format is "raw".

In "raw" format, each line of the output represents an app, which is a JSON string that could be deserialized to an `App` object.

.. code:: python

   from idf_build_apps import AppDeserializer

   with open("output.txt", "r") as f:
       for line in f:
           app = AppDeserializer.from_json(line)

In "json" format, the output is a JSON array of `App` objects.

To save the output to a file in "json" format, you can either pass the filename endswith "json", or use the ``--output-format json`` option.

.. code:: shell

   idf-build-apps find --recursive --output output.json
   idf-build-apps find --recursive --output file --output-format json
