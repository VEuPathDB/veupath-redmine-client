#!env python3
# See the NOTICE file distributed with this work for additional information
# regarding copyright ownership.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A few utils to handle organisms and organism abbreviations."""

__all__ = [
    "InvalidOrganism",
    "InvalidAbbrev",
    "OrgsUtils",
]


from os import PathLike
from pathlib import Path
import re
from typing import Set, Union


class InvalidOrganism(Exception):
    """Raised for invalid organism name."""
    def __init__(self, org, added_message="") -> None:
        message = f"Invalid organism name: '{org}'"
        if added_message:
            message += f" ({added_message})"
        super().__init__(message)


class InvalidAbbrev(Exception):
    """Raised for invalid organism abbreviation."""
    def __init__(self, abbrev, added_message="") -> None:
        message = f"Invalid organism abbrev: '{abbrev}'"
        if added_message:
            message += f" ({added_message})"
        super().__init__(message)


class OrgsUtils:
    """Collection of methods to check organism names and abbreviations."""
    abbrev_format = r"^([a-z]{4}|[a-z]sp)[A-z0-9_.-]+$"

    @staticmethod
    def validate_abbrev(abbrev: str) -> None:
        """Raises InvalidAbbrev if the abbrev format is not valid."""
        if not re.match(OrgsUtils.abbrev_format, abbrev):
            raise InvalidAbbrev(abbrev, f"does not follow the format '{OrgsUtils.abbrev_format}'")

    @staticmethod
    def generate_abbrev(name) -> str:
        """Generates an organism abbrev from a full scientific name.
        
        Raises InvalidOrganism if the input name is incorrect."""
        name = name.strip()
        if name == "":
            raise InvalidOrganism(name, "field is empty")
        items = name.split(" ")
        if len(items) < 3:
            raise InvalidOrganism(name, "name is too short")

        genus = items[0]
        species = items[1]
        if species == "sp.":
            species = "sp"

        if items[2] in ("var.", "f."):
            var = items[3]
            strain_abbrev = "".join(items[4:])
        else:
            var = ""
            strain_abbrev = "".join(items[2:])

        genus = re.sub(r"[\[\]]", "", genus)
        strains_pattern = r"(isolate|strain|breed|str\.|subspecies|sp\.)"
        strain_abbrev = re.sub(strains_pattern, "", strain_abbrev, flags=re.IGNORECASE)
        strain_abbrev = re.sub(r"[\/\(\)#:+-]", "", strain_abbrev)

        org_list = (genus[0].lower(), species[0:3], var[0:3], strain_abbrev)
        organism_abbrev = "".join(org_list)

        OrgsUtils.validate_abbrev(organism_abbrev)

        return organism_abbrev

    @staticmethod
    def load_abbrevs(abbrev_path: Union[PathLike, None] = None) -> Set[str]:
        """Returns all abbreviations from a file (one per line, no spaces). Returns empty set if no file.

        Raises:
            ValueError: raised if the file formatting is incorrect.
        """
        if not abbrev_path:
            return set()

        abbrevs_list = []
        with Path(abbrev_path).open("r") as abbrev_file:
            for line in abbrev_file:
                if re.search("\t| ", line):
                    raise ValueError("Abbreviation file contains spaces or columns")
                abbrev = line.strip().lower()
                abbrevs_list.append(abbrev)
        abbrevs = set(abbrevs_list)

        print(f"{len(abbrevs)} abbreviations loaded")

        return abbrevs
