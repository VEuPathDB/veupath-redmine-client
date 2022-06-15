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
import json
from .issue_utils import IssueUtils


class DatatypeException(Exception):
    pass


class MissingDataException(Exception):
    pass


class Genome:
    """Genome metadata representing to a Redmine issue."""

    supported_datatypes = (
        "Genome sequence and Annotation",
        "Assembled genome sequence without annotation",
    )
    insdc_pattern = r'^GC[AF]_\d{9}(\.\d+)?$'

    def __init__(self, issue):
        self.issue = issue
        self.custom = IssueUtils.get_custom_fields(self.issue)
        self.gff = ""
        self.is_replacement = False
        self.operations = []
        self.component = ""
        self.organism_abbrev = ""
        self.accession = ""
        self.errors = []
    
    def to_json(self) -> str:
        data = {
            "BRC4": {
                "component": self.component,
                "organism_abbrev": self.organism_abbrev,
            },
            "species": {},
            "assembly": {
                "accession": self.accession
            },
            "genebuild": {},
        }
        return json.dumps(data)
    
    def __str__(self) -> str:
        line = f"{IssueUtils.tostr(self.issue)} = {self.component}: {self.organism_abbrev}"
        line = line + f" - {', '.join(self.operations)}"
        if self.errors:
            line = line + f' (ERRORS: {", ".join(self.errors)})'
        else:
            line = line + ' (valid issue)'
        return line
    
    def short_str(self) -> str:
        desc = "; ".join(self.errors) if self.errors else "VALID"
        issue = self.issue
        operations = self.operations
        gff = " +GFF" if self.gff else ""
        stable_ids = " +STABLE_IDS" if "Allocate stable ids" in self.operations else ""
        replace = " +REPLACE" if self.is_replacement else ""
        ops = ",".join(operations)
        desc = f"{desc} ({ops}{gff}{stable_ids}{replace})"
        return f"  {desc:64}\t{issue.id:8}  {issue.subject}"
    
    def _add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def parse(self) -> None:
        """
        Given a Veupath Redmine genome issue, extracts relevant data
        """
        
        # First, check that it is supposed to be a genome issue
        
        # Next, check the datatype
        if self.custom["DataType"] not in self.supported_datatypes:
            raise DatatypeException(self.custom["DataType"])

        # Next, get the data
        self.parse_genome()

    def parse_genome(self) -> None:
        """
        Extract genome metadata from a Redmine issue
        """
        self._get_component()
        self._get_organism_abbrev()
        self._get_insdc_accession()
        self._get_operations()
        self._get_gff()
        self._get_replacement()
    
    def _check_accession(self, accession: str) -> str:
        """
        Check the accession string format.

        Args:
            accession: accession to check
        
        Returns:
            A valid INSDC accession, or an empty string
        """
        accession = accession.strip()
        
        # Remove the url if it's in one
        # There might even be a trailing url
        accession = re.sub(r'^.+/([^/]+)/?', r'\1', accession)

        if re.match(self.insdc_pattern, accession):
            return accession
        else:
            return ""
    
    def _get_insdc_accession(self) -> None:
        accession = self.custom["GCA number"]
        if not accession:
            self._add_error("INSDC accession missing")
            return

        accession = self._check_accession(accession)
        if not accession:
            self._add_error("Wrong INSDC accession format")
        else:
            self.accession = accession

    def _get_component(self) -> None:
        components = self.custom["Component DB"]
        if len(components) == 1:
            self.component = components[0]
        elif len(components) == 0:
            self._add_error("No component")
        elif len(components) > 1:
            self._add_error("Several components")
    
    def _get_organism_abbrev(self) -> None:
        abbrev = self.custom["Organism Abbreviation"]
        if abbrev:
            # Check before loading
            abbrev = abbrev.strip()
            if not self._check_organism_abbrev(abbrev):
                self._add_error(f"Invalid organism_abbrev: {abbrev}")
            else:
                self.organism_abbrev = abbrev
        else:
            # Also check if it can be generated from the field 'Experimental Organisms'
            if self._get_experimental_organism():
                self._add_error("Missing organism_abbrev, auto ok")
            else:
                self._add_error("Missing organism_abbrev, no auto")

    def _get_experimental_organism(self) -> str:
        return self.custom["Experimental Organisms"]

    def _get_operations(self) -> None:
        operations = self.custom["EBI operations"]
        if operations:
            self.operations = operations
        else:
            self._add_error("Missing operation")
    
    @staticmethod
    def _check_organism_abbrev(name) -> bool:
        """Basic check for organism_abbrev format."""
        if re.search(r'^([A-Za-z0-9_.-]+)$', name):
            return True
        else:
            return False

    def _get_gff(self) -> None:
        gff_path = self.custom["GFF 2 Load"]
        if gff_path:
            self.gff = gff_path

    def _get_replacement(self) -> None:
        if self.custom["Replacement genome?"].startswith("Yes"):
            self.is_replacement = True
