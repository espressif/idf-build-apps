#########################################
 Manifest File ``.build-test-rules.yml``
#########################################

A ``.build-test-rules.yml`` file is the manifest file to control whether the app will be built or tested under the rules.

One typical manifest file look like this:

.. code:: yaml

   [folder]:
     enable:
       - if: [if clause]
         temporary: true  # optional, default to false. `reason` is required if `temporary` is true
         reason: [your reason]  # optional
       - ...
     disable:
       - if: [if clause]
       - ...
     disable_test:
       - if: [if clause]
       - ...

*******
 Terms
*******

Supported Targets
=================

This refers to the targets that are fully supported by the ESP-IDF project. You may check the supported targets by running ``idf.py --list-targets``.

``idf-build-apps`` will get this information dynamically from your ``$IDF_PATH``. For ESP-IDF release 5.3, the supported targets are:

-  esp32
-  esp32s2
-  esp32c3
-  esp32s3
-  esp32c2
-  esp32c6
-  esp32h2
-  esp32p4

Preview Targets
===============

This refers to the targets that are still in preview status. You may check the preview targets by running ``idf.py --list-targets --preview``.

``idf-build-apps`` will get this information dynamically from your ``$IDF_PATH``. For ESP-IDF release 5.3, the preview targets are:

-  linux
-  esp32c5
-  esp32c61

****************
 ``if`` Clauses
****************

Operands
========

-  Capitalized Words

   -  Variables defined in ``IDF_PATH/components/soc/[TARGET]/include/soc/*_caps.h`` or in ``IDF_PATH/components/esp_rom/[TARGET]/*_caps.h``. e.g., ``SOC_WIFI_SUPPORTED``, ``ESP_ROM_HAS_SPI_FLASH``
   -  ``IDF_TARGET``
   -  ``IDF_VERSION`` (IDF_VERSION_MAJOR.IDF_VERSION_MINOR.IDF_VERSION_PATCH. e.g., 5.2.0. Will convert to Version object to do a version comparison instead of a string comparison)
   -  ``IDF_VERSION_MAJOR``
   -  ``IDF_VERSION_MINOR``
   -  ``IDF_VERSION_PATCH``
   -  ``INCLUDE_DEFAULT`` (The default value of supported targets is 1, and the default value of preview targets is 0)
   -  ``CONFIG_NAME`` (config name defined in :doc:`../explanations/config_rules`)
   -  environment variables, default to ``0`` if not set

-  String, must be double-quoted. e.g., ``"esp32"``, ``"12345"``

-  Integer, support decimal and hex. e.g., ``1``, ``0xAB``

-  List of strings or integers, or both types at the same time. e.g., ``["esp32", 1]``

Operators
=========

-  ``==``, ``!=``, ``>``, ``>=``, ``<``, ``<=``
-  ``and``, ``or``
-  ``in``, ``not in`` with list
-  parentheses

Limitations
===========

All operators are binary operators. For more than two operands, you may use the nested parentheses trick. For example:

-  ``A == 1 or (B == 2 and C in [1,2,3])``
-  ``(A == 1 and B == 2) or (C not in ["3", "4", 5])``

.. warning::

   Chained ``and`` and ``or`` operators are not supported. The operands start from the third one will be ignored.

   For example, ``A == 1 and B == 2 and C == 3`` will be interpreted as ``A == 1 and B == 2``.

**********************
 Enable/Disable Rules
**********************

By default, we enable build and test for all supported targets. In other words, all preview targets are disabled.

To simplify the manifest file, if an app needs to be build and tested on all supported targets, it does not need to be added in a manifest file. The manifest files are files that set the violation rules for apps.

Three rules (disable rules are calculated after the enable rules):

-  ``enable``: run CI build/test jobs for targets that match any of the specified conditions only
-  ``disable``: will not run CI build/test jobs for targets that match any of the specified conditions
-  ``disable_test``: will not run CI test jobs for targets that match any of the specified conditions

Each key is a folder. The rule will recursively apply to all apps inside.

Overrides Rules
===============

If one sub folder is in a special case, you can overwrite the rules for this folder by adding another entry for this folder itself. Each folder’s rules are standalone, and will not inherit its parent’s rules. (YAML inheritance is too complicated for reading)

For example, in the following code block, only ``disable`` rule exists in ``examples/foo/bar``. It’s unaware of its parent’s ``enable`` rule.

.. code:: yaml

   examples/foo:
     enable:
       - if: IDF_TARGET == "esp32"

   examples/foo/bar:
     disable:
       - if: IDF_TARGET == "esp32s2"

*******************
 Practical Example
*******************

Here’s a practical example:

.. code:: yaml

   examples/foo:
     enable:
       - if IDF_TARGET in ["esp32", 1, 2, 3]
       - if IDF_TARGET not in ["4", "5", 6]
     # should be run under all targets!

   examples/bluetooth:
     disable:  # disable both build and tests jobs
       - if: SOC_BT_SUPPORTED != 1
       # reason is optional if there's no `temporary: true`
     disable_test:
       - if: IDF_TARGET == "esp32"
         temporary: true
         reason: lack of ci runners  # required when `temporary: true`

   examples/bluetooth/test_foo:
     # each folder's settings are standalone
     disable:
       - if: IDF_TARGET == "esp32s2"
         temporary: true
         reason: no idea
     # unlike examples/bluetooth, the apps under this folder would not be build nor test for "no idea" under target esp32s2

   examples/get-started/hello_world:
     enable:
       - if: IDF_TARGET == "linux"
         reason: this one only supports linux!

   examples/get-started/blink:
     enable:
       - if: INCLUDE_DEFAULT == 1 or IDF_TARGET == "linux"
         reason: This one supports all supported targets and linux

**********************
 Enhanced YAML Syntax
**********************

Switch-Like Clauses
===================

The Switch-Like clauses are supported by two keywords in the YAML file: ``depends_components`` and ``depends_filepatterns``.

Operands
--------

Switch cases have two main components: the ``if`` clause and the ``default`` clause. Just like a switch statement in c language, The first matched ``if`` clause will be applied. If no ``if`` clause matched, the ``default`` clause will be applied. Here’s an example:

.. code:: yaml

   test1:
     depends_components:
       - if: IDF_VERSION == "{IDF_VERSION}"
         content: [ "component_1" ]
       - if: CONFIG_NAME == "AWESOME_CONFIG"
         content: [ "component_2" ]
       - default: [ "component_3", "component_4" ]

``default`` clause is optional. If you don’t specify any ``default`` clause, it will return an empty array.

Limitations
-----------

You cannot combine a list and a switch in one node.

Reuse Lists
===========

To reuse the items defined in a list, you can use the ``+`` and ``-`` postfixes respectively. The order of calculation is always ``+`` first, followed by ``-``.

Array Elements as Strings
-------------------------

The following YAML code demonstrates how to reuse the elements from a list of strings:

.. code:: yaml

   .base_depends_components: &base-depends-components
     depends_components:
       - esp_hw_support
       - esp_rom
       - esp_wifi

   examples/wifi/coexist:
     <<: *base-depends-components
     depends_components+:
       - esp_coex
     depends_components-:
       - esp_rom

After interpretation, the resulting YAML will be:

.. code:: yaml

   examples/wifi/coexist:
     depends_components:
       - esp_hw_support
       - esp_wifi
       - esp_coex

This means that the ``esp_rom`` element is removed, and the ``esp_coex`` element is added to the ``depends_components`` list.

Array Elements as Dictionaries
------------------------------

In addition to reuse elements from a list of strings, you can also perform these operations on a list of dictionaries. The matching is done based on the ``if`` key. Here’s an example:

.. code:: yaml

   .base: &base
     enable:
       - if: IDF_VERSION == "5.2.0"
       - if: IDF_VERSION == "5.3.0"

   foo:
     <<: *base
     enable+:
       # this if statement dictionary will override the one defined in `&base`
       - if: IDF_VERSION == "5.2.0"
         temp: true
       - if: IDF_VERSION == "5.4.0"
         reason: bar

After interpretation, the resulting YAML will be:

.. code:: yaml

   foo:
     enable:
     - if: IDF_VERSION == "5.3.0"
     - if: IDF_VERSION == "5.2.0"
       temp: true
     - if: IDF_VERSION == "5.4.0"
       reason: bar

In this case, the ``enable`` list is extended with the new ``if`` statement and ``reason`` dictionary.

It’s important to note that the ``if`` dictionary defined in the ``+`` postfix will override the earlier one when the ``if`` statement matches.

This demonstrates how you can use the ``+`` and ``-`` postfixes to extend and remove elements from both string and dictionary lists in our YAML.
