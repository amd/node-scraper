from errorscraper.models import DataModel


class PackageDataModel(DataModel):
    """Pacakge data contains the package data for the system

    Attributes:
        version_info (dict[str, str]): The version information for the package
            Key is the package name and value is the version of the package
    """

    version_info: dict[str, str]
