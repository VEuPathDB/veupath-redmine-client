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
"""Redmine issue object for RNA-Seq datatype."""

import re
from typing import Any, Dict, List

from unidecode import unidecode

from .issue_utils import IssueUtils
from .redmine_issue import RedmineIssue, DatatypeException


NON_ASCII = r"[^A-Za-z0-9_.-]"


class SamplesParsingException(Exception):
    """Raised when an error happens when parsing an RNA-Seq issue."""


class RNAseq(RedmineIssue):
    """RNA-Seq metadata representing a Redmine issue."""

    supported_datatypes = ("RNA-seq",)

    def __init__(self, issue):
        super().__init__(issue)
        self.dataset_name = ""
        self.samples = []
        self.no_spliced = False
        self.is_ref_change = False
        if "Reference change" in self.operations:
            self.is_ref_change = True
        self.new_genome = False

        valid_operations = {"Other", "Reference change", "Patch build"}
        operations = self.operations.copy()
        for operation in operations:
            if operation not in valid_operations:
                self.operations.remove(operation)

    def to_json_struct(self) -> Dict[str, Any]:
        """Returns a structure representation of the RNA-Seq data of the issue following the json schema."""
        data: Dict[str, Any] = {
            "component": "",
            "species": "",
            "name": "",
            "runs": [],
        }
        if self.component:
            data["component"] = self.component
        if self.organism_abbrev:
            data["species"] = self.organism_abbrev
        if self.dataset_name:
            data["name"] = self.dataset_name
        if self.samples:
            data["runs"] = self.samples
        if self.no_spliced:
            data["no_spliced"] = True

        return data

    def __str__(self) -> str:
        line = f"{IssueUtils.tostr(self.issue)} = {self.component}: {self.organism_abbrev}"
        if self.errors:
            line = line + f' (ERRORS: {", ".join(self.errors)})'
        else:
            line = line + " (valid issue)"
        if self.is_ref_change:
            line += " (Reference change)"
        return line

    def short_str(self) -> str:
        """Returns a short representation of the RNA-Seq issue."""
        # status
        if self.errors:
            status = "BAD"
        else:
            status = "ok"

        # Create description
        descriptions = self.operations.copy()
        if self.new_genome:
            descriptions.add("New genome")
        desc = ",".join(descriptions)

        # Organism abbrev
        if self.organism_abbrev:
            organism_str = self.organism_abbrev
        else:
            organism_str = "no organism_abbrev"

        # Component
        if self.component:
            component_str = self.component
            if len(component_str) > 12:
                component_str = component_str[0:9] + "..."
        else:
            component_str = "no component"

        # Dataset
        if self.dataset_name:
            dataset_str = self.dataset_name
            if len(dataset_str) > 24:
                dataset_str = dataset_str[0:24] + "..."
        else:
            dataset_str = "no dataset_name"

        # Subject
        issue = self.issue
        subject = issue.subject
        if len(subject) > 40:
            subject = subject[0:37] + "..."

        # Merge all
        line = (
            f"{status:3}  {issue.id:6}  {component_str:12}  "
            f"{organism_str:24}  {dataset_str:24}  {desc:22}  {subject}"
        )
        errors = "\n".join([(" " * 13) + f"ERROR: {error}" for error in self.errors])
        if errors:
            line = f"{line}\n{errors}"
        return line

    def parse(self) -> None:
        """Extract and store the relevant data from an RNA-Seq issue."""
        # Check the datatype
        if self.custom["DataType"] not in self.supported_datatypes:
            raise DatatypeException(self.custom["DataType"])

        # Next, get the data
        if self.is_ref_change or "Other" in self.operations or "Patch build" in self.operations:
            self.disable_log()

        self._get_dataset_name()
        self._get_samples()
        self.enable_log()

    def _get_dataset_name(self) -> None:
        """Store the dataset name from the issue. Store any error."""
        name = self.custom["Internal dataset name"]
        if name:
            name = name.strip()
            self.dataset_name = name
            if re.search(NON_ASCII, name):
                self.add_error(f"Bad chars in dataset name: '{name}'")
        else:
            self.add_error("Missing dataset name")

    def _get_samples(self) -> None:
        """Store the samples from the issue. Store any error."""
        samples_str = self.custom["Sample Names"]
        if samples_str:
            samples = self._parse_samples(samples_str)
            if samples:
                self.samples = samples
            else:
                self.add_error("Wrong sample format")
        else:
            self.add_error("Missing samples")

    def _parse_samples(self, sample_str: str) -> List[Dict]:
        """Parse a list of samples from a Redmine task.

        Args:
            sample_str: The value of the field 'Sample Names' from an RNA-Seq Redmine task.

        Returns:
            A list of samples dicts, with the following keys:
                name: the name of the sample.
                accessions: a list of string representing the SRA accessions for that sample.
        """
        samples = []

        # Parse each line
        lines = sample_str.split("\n")

        try:
            sample_names = {}
            accessions_count: dict = {}
            sample_errors = []
            for line in lines:
                line = line.strip()
                if line == "":
                    continue

                # Get sample_name -> accessions
                parts = line.split(":")
                if len(parts) > 2:
                    end = parts[-1]
                    start = ":".join(parts[:-1])
                    parts = [start, end]

                if len(parts) == 2:
                    sample_name = parts[0].strip()

                    if sample_name in sample_names:
                        sample_errors.append(f"repeated name {sample_name}")
                        continue
                    sample_names[sample_name] = True

                    accessions_str = parts[1].strip()
                    accessions = [x.strip() for x in accessions_str.split(",")]

                    if not self._validate_accessions(accessions):
                        if self._validate_accessions(sample_name.split(",")):
                            sample_errors.append(f"name and accession switched? ({line})")
                            continue
                        sample_errors.append(f"Invalid accession in '{accessions}' ({line})")
                        continue

                    # Check uniqueness of SRA ids within this dataset
                    for accession in accessions:
                        if accession in accessions_count:
                            accessions_count[accession] += 1
                        else:
                            accessions_count[accession] = 1
                    norm_name = ""
                    try:
                        norm_name = self._normalize_name(sample_name)
                    except SamplesParsingException:
                        sample_errors.append(f"sample name can't be normalized ({line})")
                        continue
                    sample = {"name": norm_name, "accessions": accessions}
                    samples.append(sample)
                else:
                    sample_errors.append(f"sample line doesn't have 2 parts ({line})")
                    continue

            duplicated = []
            for accession, count in accessions_count.items():
                if count > 1:
                    duplicated.append(f"{accession} (x{count})")
            if duplicated:
                raise SamplesParsingException(
                    f"{len(duplicated)} accessions duplicates: {'; '.join(duplicated)}"
                )

            if sample_errors:
                raise SamplesParsingException(f"{len(sample_errors)} errors: {'; '.join(sample_errors)}")
        except SamplesParsingException as e:
            self.add_error(str(e))

        return samples

    def _validate_accessions(self, accessions: List[str]) -> bool:
        """Check SRA accessions format, to make sure we get proper ones.

        Args:
            accessions: a list of strings to check

        Return:
            True if all strings are proper SRA accessions.
            False if at least one is not a proper SRA accession.
        """
        if "" in accessions:
            return False
        for acc in accessions:
            if not re.search(r"^[SED]R[RSXP]\d+$", acc):
                return False
        return True

    @staticmethod
    def _normalize_name(old_name: str) -> str:
        """Remove special characters from a name, keep ascii only.

        Args:
            old_name: the name to format.

        Returns:
            The formatted name.
        """

        # Remove any diacritics
        name = old_name.strip()
        name = unidecode(name)
        name = re.sub(r"[ /]", "_", name)
        name = re.sub(r"[;:.,()\[\]{}]", "", name)
        name = re.sub(r"\+", "_plus_", name)
        name = re.sub(r"\*", "_star_", name)
        name = re.sub(r"%", "pc_", name)
        name = re.sub(r"_+", "_", name)
        if re.search(NON_ASCII, name):
            raise SamplesParsingException(f"name contains special characters: {old_name} ({name})")
            name = ""

        return name
