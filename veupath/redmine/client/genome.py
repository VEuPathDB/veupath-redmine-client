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
from typing import Any, Dict
from .issue_utils import IssueUtils
from .redmine_issue import RedmineIssue, DatatypeException


class Genome(RedmineIssue):
    """Genome metadata representing a Redmine issue."""

    supported_datatypes = (
        "Genome sequence and Annotation",
        "Assembled genome sequence without annotation",
    )
    insdc_pattern = r'^GC[AF]_\d{9}(\.\d+)?$'

    def __init__(self, issue):
        super().__init__(issue)
        self.gff = ""
        self.is_replacement = False
        self.operations = []
        self.accession = ""
        self.annotated = self._is_annotated()
    
    def _is_annotated(self) -> bool:
        if self.datatype == "Genome sequence and Annotation":
            return True
        elif self.datatype == "Assembled genome sequence without annotation":
            return False
        else:
            self._add_error(f"unsupported datatype for genome: {self.datatype}")
            return False
    
    def to_json_struct(self) -> Dict[str, Any]:
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
        return data
    
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
        desc = f"{desc}\t({ops}{gff}{stable_ids}{replace})"
        subject = issue.subject
        if self.organism_abbrev:
            subject = f"{self.organism_abbrev:20}  {subject}"
        if len(subject) > 80:
            subject = subject[0:80] + '...'
        return f"  {desc:64}  {issue.id:8} {subject}"
    
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
        self._get_experimental_organism()
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

    def _get_operations(self) -> None:
        try:
            operations = self.custom["EBI operations"]
        except KeyError:
            operations = []

        if operations:
            self.operations = operations
        else:
            self._add_error("Missing operation")
    
    def _get_gff(self) -> None:
        try:
            gff_path = self.custom["GFF 2 Load"]
        except KeyError:
            gff_path = ""

        if gff_path:
            self.gff = gff_path

    def _get_replacement(self) -> None:
        try:
            replace = self.custom["Replacement genome?"]
        except KeyError:
            replace = ""

        if replace.startswith("Yes"):
            self.is_replacement = True

    def check_datatype(self, email: str = '') -> None:
        """
        Check if we expect an annotation with a gff from INSDC/GFF2Load
        """

        if email:
            print(f"Check Entrez for {self.accession}")
        else:
            has_gff = False
            if self.gff:
                has_gff = True
            if has_gff and not self.annotated:
                self._add_error("Got a gff but not expected to be annotated")
            # if not has_gff and self.annotated:
            #     self._add_error("Got no gff but expected to be annotated")
