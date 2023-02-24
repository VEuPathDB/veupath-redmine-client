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
from Bio import Entrez
from Bio.Entrez.Parser import ValidationError


class Genome(RedmineIssue):
    """Genome metadata representing a Redmine issue."""

    supported_datatypes = (
        "Genome sequence and Annotation",
        "Assembled genome sequence without annotation",
        "Gene Models",
    )
    insdc_pattern = r'^GC[AF]_\d{9}(\.\d+)?$'
    refseq_pattern = r'^GCF_\d{9}(\.\d+)?$'

    def __init__(self, issue):
        super().__init__(issue)
        self.gff = ""
        self.is_replacement = False
        self.accession = ""
        self.annotated = self._is_annotated()
        self.insdc_metadata = dict()
    
    def _is_annotated(self) -> bool:
        if self.datatype == "Genome sequence and Annotation":
            return True
        else:
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
        
        # First, check the datatype
        if self.custom["DataType"] not in self.supported_datatypes:
            raise DatatypeException(f"Datatype not supported: '{self.custom['DataType']}'")

        # Next, get the data
        if "Patch build" in self.operations:
            self.is_replacement = True
            return
        else:
            self.parse_genome()

    def parse_genome(self) -> None:
        """
        Extract genome metadata from a Redmine issue
        """
        self._get_insdc_accession()
        self._get_gff()
        self._get_replacement()
        self._get_insdc_metadata()
        self._check_datatype()
    
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
            if "Load from RefSeq" in self.operations and not re.match(self.refseq_pattern, accession):
                self.add_error(f"Accession {accession} is not a RefSeq accession")
            elif "Load from INSDC" in self.operations and re.match(self.refseq_pattern, accession):
                self.add_error(f"Accession {accession} is a RefSeq accession, not INSDC")
            return accession
        else:
            return ""
    
    def _get_insdc_accession(self) -> None:
        accession = self.custom["GCA number"]
        if not accession:
            self.add_error("INSDC accession missing")
            return

        accession = self._check_accession(accession)
        if not accession:
            self.add_error("Wrong INSDC accession format")
        else:
            self.accession = accession
    
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
    
    def _get_insdc_metadata(self) -> Dict[str, Any]:
        if self.insdc_metadata:
            return self.insdc_metadata

        summary: Dict[str, Any] = dict()
        if Entrez.email and self.accession:
            handle = Entrez.esearch(db="assembly", term=self.accession, retmax='5')
            try:
                record = Entrez.read(handle)
            except ValidationError:
                self.errors("Validation error")
                return summary
            ids = record["IdList"]

            if len(ids) == 0:
                self.add_error("Assembly not found in INSDC")
            else:
                if len(ids) > 1:
                    print(f"{len(ids)} assemblies found for {self.accession}, using the first one ({ids[0]})")
                id = ids[0]
                summary_full = self.get_assembly_metadata(id)
                summary = summary_full["DocumentSummarySet"]["DocumentSummary"][0]
                self.insdc_metadata = summary
        return summary

    def get_assembly_metadata(self, id):
        esummary_handle = Entrez.esummary(db="assembly", id=id, report="full")
        esummary_record = Entrez.read(esummary_handle)
        return esummary_record

    def assembly_is_annotated(self) -> bool:
        properties = self.insdc_metadata["PropertyList"]
        if self.accession.startswith("GCA") and "has_annotation" in properties:
            return True
        elif self.accession.startswith("GCF") and "refseq_has_annotation" in properties:
            return True
        else:
            return False

    def _check_datatype(self) -> None:
        """
        Check if we expect an annotation with a gff from INSDC/GFF2Load
        """
        if not self.insdc_metadata:
            return
        if "Load from EnsEMBL" in self.operations:
            return

        has_gff = False
        if self.gff:
            has_gff = True
        is_annotated = self.assembly_is_annotated()
        
        if (has_gff or is_annotated) and not self.annotated:
            self.add_error("Got a gff but not expected to be annotated")
        if not (has_gff or is_annotated) and self.annotated:
            self.add_error("Got no gff but expected to be annotated")

