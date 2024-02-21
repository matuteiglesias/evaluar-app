import pkg_resources



installed_packages = [(d.project_name, d.version) for d in pkg_resources.working_set]

installed_packages