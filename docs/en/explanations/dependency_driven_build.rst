#########################
 Dependency-Driven Build
#########################

In large projects or monorepos, it is often desirable to only run builds and tests which are somehow related to the changes in a pull request.

idf-build-apps supports this by checking whether a particular app has been modified, or depends on modified components or modified files. This check is based on the knowledge of two things: the list of components/files the app depends on, and the list of components/app which are modified in the pull request.

.. note::

   For detailed list of arguments, please refer to the :class:`~idf_build_apps.args.DependencyDrivenBuildArguments` reference.

.. _basic-usage:

*************
 Basic Usage
*************

To enable this feature, the simplest way is to pass ``--modified-components`` to the ``idf-build-apps build`` command.

While building the app, ``idf-build-apps`` will first run ``idf.py reconfigure``. ``idf.py reconfigure`` will run the first-step of the build system, which will determine the list of components the app depends on. Then, ``idf-build-apps`` will compare the list of modified components with the list of components the app depends on. If any of the modified components are present in the list of dependencies, the app will be built.

For example, if we run

.. code:: bash

   cd $IDF_PATH/examples/get-started/hello_world
   idf-build-apps build -t esp32 --modified-components fake

We'll see the following output:

.. code:: text

   (cmake) App ., target esp32, sdkconfig (default), build in ./build, skipped in 4.271822s: app . depends components: {'esp_app_format', 'esp_driver_sdmmc', 'esp_driver_gpio', 'esp_common', 'esp_driver_parlio', 'esp_http_client', 'esp-tls', 'heap', 'app_trace', 'esp_driver_rmt', 'bt', 'esp_driver_ana_cmpr', 'esptool_py', 'wear_levelling', 'esp_driver_ppa', 'esp_driver_cam', 'unity', 'usb', 'app_update', 'esp_driver_spi', 'protocomm', 'esp_ringbuf', 'esp_security', 'bootloader', 'freertos', 'idf_test', 'vfs', 'hal', 'log', 'nvs_flash', 'esp_system', 'esp_driver_sdio', 'rt', 'efuse', 'esp_https_ota', 'espcoredump', 'esp_timer', 'esp_adc', 'esp_local_ctrl', 'xtensa', 'nvs_sec_provider', 'esp_pm', 'esp_gdbstub', 'lwip', 'json', 'partition_table', 'ulp', 'mbedtls', 'wifi_provisioning', 'esp_driver_sdspi', 'esp_vfs_console', 'esp_partition', 'soc', 'esp_psram', 'esp_eth', 'perfmon', 'sdmmc', 'esp_driver_usb_serial_jtag', 'esp_driver_dac', 'esp_driver_jpeg', 'esp_lcd', 'esp_driver_i2s', 'esp_driver_pcnt', 'ieee802154', 'esp_driver_i2c', 'spiffs', 'esp_driver_tsens', 'driver', 'mqtt', 'main', 'tcp_transport', 'newlib', 'openthread', 'esp_hid', 'esp_driver_gptimer', 'fatfs', 'protobuf-c', 'esp_netif', 'esp_rom', 'cxx', 'esp_bootloader_format', 'esp_wifi', 'esp_driver_ledc', 'pthread', 'esp_phy', 'esp_driver_touch_sens', 'http_parser', 'esp_https_server', 'bootloader_support', 'esp_hw_support', 'esp_event', 'esp_driver_uart', 'esp_netif_stack', 'cmock', 'spi_flash', 'esp_driver_sdm', 'esp_coex', 'esp_driver_isp', 'esp_mm', 'esp_driver_mcpwm', 'wpa_supplicant', 'esp_http_server', 'console'}, while current build modified components: ['fake']

The app is skipped because it does not depend on the modified component `fake`.

************************************
 Customize the Dependency of an App
************************************

.. note::

   If you're unfamiliar with the manifest file, please refer to the :doc:`Manifest File Reference <../references/manifest>`.

To customize the dependencies of an app, `idf-build-apps` supports declaring the dependencies in the manifest files with the `depends_components` and `depends_filepatterns` fields. ``idf-build-apps`` will build the app in the following conditions:

-  any of the files under the app directory are modified, except for the ``.md`` files.
-  any of the modified components are listed in the ``depends_components`` field. (if ``depends_components`` specified)
-  any of the modified components are listed in the ``idf.py reconfigure`` output. (if ``depends_components`` not specified, as explained in the :ref:`previous section <basic-usage>`)
-  any of the modified files are matched by the ``depends_filepatterns`` field.

Here is an example of a manifest file:

.. code:: yaml

   # rules.yml
   examples/foo:
     depends_components:
       - comp1
       - comp2
       - comp3
     depends_filepatterns:
       - "common_header_files/**/*"

The apps under folder ``examples/foo`` will be built with the following CLI options:

-  ``--manifest-files rules.yml --modified-files examples/foo/main/foo.c``

   modified file is under the app directory

-  ``--manifest-files rules.yml --modified-components comp1``

   modified component is listed in the ``depends_components`` field

-  ``--manifest-files rules.yml --modified-components comp2;comp4 --modified-files /tmp/foo.h``

   modified component is listed in the ``depends_components`` field

-  ``--manifest-files rules.yml --modified-files common_header_files/foo.h``

   modified file is matched by the ``depends_filepatterns`` field

-  ``--manifest-files rules.yml --modified-components comp4 --modified-files common_header_files/foo.h``

   modified file is matched by the ``depends_filepatterns`` field

The apps will not be built with the following CLI options:

-  ``--manifest-files rules.yml --modified-files examples/foo/main/foo.md``

   only the ``.md`` files are modified

-  ``--manifest-files rules.yml --modified-components bar``

   modified component is not listed in the ``depends_components`` field

-  ``--modified-components comp1``

   ``--manifest-files`` is not passed

The entries in the manifest files are relative paths. By default they are relative to the current working directory. If you want to set the root directory of the manifest files, you can use the ``--manifest-rootpath`` CLI option.

**********************************************************
 Disable the Feature When Touching Low-level Dependencies
**********************************************************

Low-level dependencies, are components or files that are used by many others. For example, component ``freertos`` provides the operating system support for all apps, and ESP-IDF build system related cmake files are also used by all apps. When these items are modified, we definitely need to build and test all the apps.

To disable the dependency-driven build feature, you can use the CLI option ``--deactivate-dependency-driven-build-by-components`` or ``--deactivate-dependency-driven-build-by-filepatterns``. For example:

.. code:: bash

   idf-build-apps build -t esp32 --modified-components freertos --deactivate-dependency-driven-build-by-components freertos

This command will build all the apps, even if the apps do not depend on the component ``freertos``.
