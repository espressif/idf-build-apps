##############
 Build Status
##############

This page explains the different build statuses that apps can have during the build process and what each status means.

Each app in `idf-build-apps` has a build status that indicates its current state in the build pipeline. Understanding these statuses is crucial for interpreting build results and troubleshooting issues.

********************
 Available Statuses
********************

The following build statuses are available:

``unknown``
===========

The default status when an app is first discovered. The app's build status has not yet been determined.

This status indicates that:

-  The app has been found but not yet processed
-  Further ``idf.py reconfigure`` is needed to determine if the build can proceed

``disabled``
============

The app supports the target architecture, but has been disabled by manifest rules or configuration.

This status indicates that:

-  The app is compatible with the target but explicitly disabled
-  Manifest rules contain ``disable`` clauses that match this app and target combination

Apps with this status will not be built unless specifically included with ``--include-disabled-apps``.

``skipped``
===========

The app supports the target and could potentially be built, but has been skipped due to dependency-driven build logic or dry run mode.

This status indicates that:

-  **Dependency-driven build**: The app doesn't depend on any of the modified components/files in the current build
-  **Dry run mode**: The ``--dry-run`` flag was used, so no actual building occurs

Apps with this status will not be built unless specifically included with ``--include-skipped-apps``.

``should be built``
===================

The app should be built but hasn't been built yet.

This status indicates that:

-  The app has passed all checks and is ready for building
-  Dependency analysis shows the app should be included in this build
-  The app has not been built yet in the current run

``build failed``
================

The app build process was attempted but failed.

This status indicates that:

-  The build process started but encountered an error
-  Compilation, linking, or other build steps failed
-  The failure reason is typically available in the build comment and build logs

``build success``
=================

The app was successfully built.

This status indicates that:

-  All build steps completed without errors
-  The app binary was generated successfully
-  The build process finished normally

************************
 Status Transition Flow
************************

The typical flow of build statuses is:

#. **unknown** → Initial state when app is discovered
#. **unknown** → **disabled** (if app doesn't support target or is disabled by manifest)
#. **unknown** → **skipped** (if dependency checks show app shouldn't be built)
#. **unknown** → **should be built** (if app passes all checks)
#. **should be built** → **build failed** (if build encounters errors)
#. **should be built** → **build success** (if build completes successfully)

.. note::

   Apps in ``disabled`` or ``skipped`` status will not transition to ``should be built`` unless the conditions change or specific inclusion flags are used.

**********************
 Viewing Build Status
**********************

You can view the build status of apps in several ways:

-  **JSON output**: Use ``--json-output`` to save detailed status information
-  **Build logs**: Status and comments are included in build output
-  **Summary reports**: Final status counts are shown at the end of builds

**************************
 Including Apps by Status
**************************

By default, only apps with ``unknown``, ``should be built``, ``build failed``, and ``build success`` statuses are processed. You can include additional apps using:

-  ``--include-disabled-apps``: Include apps with ``disabled`` status
-  ``--include-skipped-apps``: Include apps with ``skipped`` status

This is useful for:

-  Testing disabled apps during development
-  Force-building apps that would normally be skipped
-  Comprehensive testing regardless of dependency analysis
