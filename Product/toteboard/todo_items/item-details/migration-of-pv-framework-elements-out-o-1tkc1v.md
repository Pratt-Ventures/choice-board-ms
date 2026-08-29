# Migration of pv framework elements out of PowerChoice base

## Short Description
### user
We are migrating logic that is part of this project and close variants in others into a standard framework that can be used by multiple application projects, but maintained separately. This reduces the footprint of the specific application project code and standardizes behavior and practices across our applications and projects.

We have moved the files and made key dependency changes, but more work remains.

The goal is a single, standard, executable, pvf/pvf_app_runner.py, a standardized variation of the current powerchoice_server.py that binds and launches an app_shell.py, that is particular to the application project. app_shell.py will be the example, but the actual name and location is configurable in a YAML file.

The application runner will open a pvf_app_startup.yaml (in the src root), where it retrieves the path/name of the file that will be loaded as a module to start the application. It will also have settings for the name of the .env file that optionally overrides or supplies environment variables. 

These could not be changed without impact on a running application and deserve first-class treatment. As of now, ACTIVATE_STRIPE_INTEGRATION and ACTIVATE_BRANDING_IMAGE_STORE are the only two, but there will be more. We will migrate the external api services, once hooks to application specific data and supporting logic are incorporated. The same will be done to the share logic, which will be changed so each share has a list of possible actions (strings) and the share record keeping is the list of actions actually used. This will need adjustments in the application and hooks to related application logic. We prefer that enums be used to define possible values to make internal patterns more clear. Similar to email services, either enums or strings, in this case a list would also be accepted, and then get coverted to a list of strings internal to the share link support.

The settings that enable major features and require application logic to interface should be moved to the YAML file. Once the configuration file is loaded, values in the YAML should be injected into the pvf.config.settings, on a read only basis. Dummy definitions, proected with readonly logic, should be added to the pfv_config settings. They can existing in both places, with update occuring as described, but only the startup logic (not .env or other sources) can set these values. The presence is informational, but unlikely to be used in an application. This will also have the module that loads all database table specifications for alembic processing. This will be called by the pvf_alembic handler to merge the sql metadata. The example logic implementation should be updated and made clean.

Variables that are fixed for deployment, such as major pfv options to enable, are specified in the YAML file, not the ordinary configuration files. We prefer the env file to simply be .env, using standard python libaries to injest, with an example in the application images as example.env. We have had issues with Alembic or the particular ingestion method in the past, so we switched to the current convention. We would prefer to change this if no issues arise. The actual name would still be a YAML configuration item, just usually the same. 

When alembic needs to determine the database configuration, it will invoke pvf_get_alembic_config.py. This reads the YAML file and orchestrates the steps to export the current SQLAlchemy/SQLModel database configuration. This should load only the paths needed to get a proper current schema, from both pvw and the application using it.

During normal execution, the pvf_application server loads the YAML file to find bindings and features to import and activate. Some activation checks are present, but the modules are always implemented today. We should consider not importing the unused modules as well.

The orchestration and sequence proposed for the process startup and bindings are:

pvf_application main process starts; a connection to the database is established first. The successful database handle is used by pvf and also passed to the application running with the framework. If unsuccessful, clear failure information is output to the console (stderr) and the process exits with an error code. 

A new file, used in client applications, will provide the bridge logic between the app runner and the pvf. The name and entry point, while a convention is likely to emerge as stated above, is controlled the YAML settings. Note the 'server.py' file needs to be refactors as part of this process. It is performing application needs, loading application specific templates. The concept is fine, this should be called by the application's startup logic, not the framework.

The application's entry point is called with a well defined PvfInvocation class object. The application is expected to make certain updates within this object. The return value is None for success or an error message. The application can also raise descriptive errors to signal failure during startup or at any time. This object has the PvfGlobalSettings Class object, active pvf_settings object, database connection object, the FastAPI objects, a list to add routers targeted at each FastAPI object, access to add metadata categories for each router, etc. Other data is added as appropriate for binding. We'd like to make better use of Dependency injection. Two new FastAPI instances should be created, one configured for no authorization expected (login page, change password, related entry points that don't have a cookie/jwt/special-headers, etc), and a distinct endpoint for share link access. So there will be no_auth FastAPI instance, logged in session instance, a share link instance, and external API instance. Dependency injection will be strictly enforced, regardless of whether the dependency data is an input parameter for the given endpoint.

The application creates its own 'settings' object, or equivalent, and, for example, not enforced, using PvfGlobalSettings as a base class for its GlobalSettings and calling a new pvf utility to merge pvf_settings contents into the global settings (in application's settings instance). The pvf_settings object is used in the pvf implementation and does not internally need access to the broader application settings.

The application then must load necessary modules (without cycles) to create schemas, both for full use and for alembic probe use. It must create application routes and add each router to the appropriate router list.

The application also needs a means to signal added columns for any table in the toolkit. This would principally be used for customer, user, possibly share or external api. Hooks or extended parameters packages (e.g., a dictionary) will be added on appropriate internal calls to allow the application to populate these fields. They are otherwise moved around and stored by pvf only. The mechanism should allow fields to be injected precisely into the field list by specifying the predecessor field. Nothing will be allowed before the standard 'id' field used in pvf tables.

When these steps are orchestrated and all routers have been added to the calling information object, the application returns. Assuming no error report, the main application completes setup, including merging application openapi entries (the application can update the supplied structure or provide (in a separate field) added values that will be merged by pvf.

All expected entry points and specific includes should be defined in the new pvf readme.md. Other imports or calls into pvf are discouraged. 


All standard entry points to pvf for the application projects that do not use REST endpoints should be provided in a single 'pvf_services.py' file in the utils directory of pvf.

The above gives a strong sense of direction, but may not be complete and may have errors or omissions. The goal is a pvf framework, in a separate subdirectory tree, pvf, under src for now, but likely packaged differently soon. Generate a plan to complete the migration, including generalizing and moving all general share link and external api capabilities to pvf. Make strong engineering choices, as senior engineers using this framework expect a strong, robust solution.


[comment: updated 2026-08-17T17:41:52.655Z | id migration-of-pv-framework-elements-out-o-1tkc1v]

## Expanded Description

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-17T17:34:53.820Z created (source: user)
