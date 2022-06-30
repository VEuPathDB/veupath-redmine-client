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


import re
from typing import Set


class InvalidAbbrev(Exception):
    pass


class OrgsUtils:

    abbrev_format = r'^([a-z]{4}|[a-z]sp)[A-z0-9_.-]+$'

    @staticmethod
    def validate_abbrev(abbrev: str) -> bool:
        if re.match(OrgsUtils.abbrev_format, abbrev):
            return True
        else:
            return False

    @staticmethod
    def generate_abbrev(name) -> str:
        
        name = name.strip()
        if name == "":
            raise Exception("field 'Experimental Organisms' needed")
        items = name.split(" ")
        if len(items) < 3:
            raise Exception(f"name is too short ({name})")

        genus = items[0]
        species = items[1]

        if items[2] in ('var.', 'f.'):
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

        valid = OrgsUtils.validate_abbrev(organism_abbrev)
        if not valid:
            raise InvalidAbbrev(f"Invalid organism abbrev generated: '{organism_abbrev}' from '{name}'")
        return organism_abbrev

    @staticmethod
    def load_abbrevs(abbrev_path: str) -> Set[str]:
        if not abbrev_path:
            return set()

        abbrevs_list = []
        with open(abbrev_path, "r") as abbrev_file:
            for line in abbrev_file:
                if re.match("\t| ", line):
                    raise Exception("Abbreviation file contains spaces or columns")
                abbrev = line.strip().lower()
                abbrevs_list.append(abbrev)
        abbrevs = set(abbrevs_list)

        print(f"{len(abbrevs)} abbreviations loaded")
        
        return abbrevs
