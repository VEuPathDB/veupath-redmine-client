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

from Bio import Entrez
from Bio.Entrez.Parser import ValidationError

from .issue_utils import IssueUtils
from .redmine_issue import RedmineIssue, DatatypeException


class Genome(RedmineIssue):
    """Genome metadata representing a Redmine issue."""

    supported_datatypes = (
        "Genome sequence and Annotation",
        "Assembled genome sequence without annotation",
        "Gene Models",
    )
    insdc_pattern = r"^GC[AF]_\d{9}(\.\d+)?$"
    refseq_pattern = r"^GCF_\d{9}(\.\d+)?$"

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
            "assembly": {"accession": self.accession},
            "genebuild": {},
        }
        return data

    def __str__(self) -> str:
        line = f"{IssueUtils.tostr(self.issue)} = {self.component}: {self.organism_abbrev}"
        line = line + f" - {', '.join(self.operations)}"
        if self.errors:
            line = line + f' (ERRORS: {", ".join(self.errors)})'
        else:
            line = line + " (valid issue)"
        return line

    def short_str(self) -> str:
        # status
        if self.errors:
            status = "BAD"
        else:
            status = "ok"

        # Create description
        operations = self.operations
        gff = " +GFF" if self.gff else ""
        replace = " +REPLACE" if self.is_replacement else ""
        ops = ",".join(operations)
        desc = f"{ops}{gff}{replace}"

        # Organism abbrev
        if self.organism_abbrev:
            organism_str = self.organism_abbrev
        else:
            organism_str = "no organism_abbrev"

        # Component
        if self.component:
            component_str = self.component
            if len(component_str) > 12:
                component_str = component_str[0:12]
        else:
            component_str = "no component"

        # Subject
        issue = self.issue
        subject = issue.subject
        if len(subject) > 64:
            subject = subject[0:64] + "..."

        # Merge all
        line = f"{status:3}  {issue.id:6}  {component_str:12}  {organism_str:24}    {desc:32}    {subject}"
        errors = "\n".join([(" " * 13) + f"ERROR: {error}" for error in self.errors])
        warnings = "\n".join([(" " * 13) + f"WARNING: {warning}" for warning in self.warnings])
        if errors:
            line = f"{line}\n{errors}"
        if warnings:
            line = f"{line}\n{warnings}"
        return line

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
        self._get_replacement()
        self._get_gff()

        self._get_insdc_accession()
        self._get_insdc_metadata()
        self._check_refseq()
        self._check_datatype()
        self._check_latest()

    def _check_latest(self) -> None:
        summary = self.insdc_metadata

        latest_accession = summary.get("LatestAccession")
        if latest_accession and latest_accession != self.accession:
            self.add_warning(f"Not the latest accession: {self.accession} -> {latest_accession}")

        anomalous = summary.get("AnomalousList")
        if anomalous:
            for anomaly in anomalous:
                self.add_warning(f"Anomaly: {anomaly['Property']}")

    def _check_accession(self, full_accession: str) -> str:
        """
        Check the accession string format.

        Args:
            full_accession: accession to check

        Returns:
            A valid INSDC accession, or an empty string
        """
        full_accession = full_accession.strip()

        # Remove the url if it's in one
        # There might even be a trailing url
        accession_str = re.sub(r"^.+/([^/]+)/?", r"\1", full_accession)
        accession, version = accession_str.split(".")

        if re.match(self.insdc_pattern, accession):
            if "Load from RefSeq" in self.operations and not re.match(self.refseq_pattern, accession):
                self.add_error(f"Accession {accession} is not a RefSeq accession")
            elif "Load from INSDC" in self.operations and re.match(self.refseq_pattern, accession):
                self.add_error(f"Accession {accession} is a RefSeq accession, not INSDC")
            elif version is None or not version.isdigit():
                self.add_error(f"Accession {full_accession} doesn't have a version number")
            return full_accession
        return ""

    def _get_insdc_accession(self) -> None:
        exclude_operations = {"Load from INSDC", "Load from RefSeq", "Load from EnsEMBL"}
        if not exclude_operations.intersection(self.operations) and self.is_replacement:
            return

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
            handle = Entrez.esearch(db="assembly", term=self.accession, retmax="5")
            try:
                record = Entrez.read(handle, validate=False)
            except ValidationError:
                self.add_error("Validation error")
                return summary
            id_list = record["IdList"]

            if len(id_list) == 0:
                self.add_error("Assembly not found in INSDC")
            else:
                for accession_id in id_list:
                    summary_full = self.get_assembly_metadata(accession_id)
                    summary = summary_full["DocumentSummarySet"]["DocumentSummary"][0]
                    if summary["AssemblyAccession"] == self.accession:
                        if len(id_list) > 1:
                            print(f"{self.accession} matched {len(id_list)} assemblies, using {accession_id}")
                        self.insdc_metadata = summary
                        break
        return summary

    def get_assembly_metadata(self, accession):
        esummary_handle = Entrez.esummary(db="assembly", id=accession, report="full")
        esummary_record = Entrez.read(esummary_handle, validate=False)
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

    def _check_refseq(self) -> None:
        """
        Check if the RefSeq assembly has been suppressed and why.
        """
        if not self.insdc_metadata:
            return

        if self.accession.startswith("GCF"):
            try:
                suppressed_reason = self.insdc_metadata["ExclFromRefSeq"]
            except KeyError:
                return
            if suppressed_reason:
                self.add_error(f"Suppressed ({', '.join(suppressed_reason)})")
