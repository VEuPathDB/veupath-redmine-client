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
from unidecode import unidecode
from typing import Any, Dict, List
from .issue_utils import IssueUtils
from .redmine_issue import RedmineIssue, DatatypeException


class SamplesParsingException(Exception):
    pass


class RNAseq(RedmineIssue):
    """RNA-Seq metadata representing a Redmine issue."""

    supported_datatypes = (
        "RNA-seq",
    )

    def __init__(self, issue):
        super().__init__(issue)
        self.dataset_name = ""
        self.samples = []
        self.no_spliced = False
    
    def to_json_struct(self) -> Dict[str, Any]:
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
            line = line + ' (valid issue)'
        return line
    
    def short_str(self) -> str:
        desc = "; ".join(self.errors) if self.errors else "VALID"
        issue = self.issue
        
        subject = issue.subject
        if len(subject) > 80:
            subject = subject[0:80] + '...'
        return f"  {desc:64}\t{issue.id:8}  {subject}"
    
    def parse(self) -> None:
        """
        Given a Veupath Redmine RNA-Seq issue, extracts relevant data
        """
        
        # Check the datatype
        if self.custom["DataType"] not in self.supported_datatypes:
            raise DatatypeException(self.custom["DataType"])

        # Next, get the data
        self.parse_rnaseq()

    def parse_rnaseq(self) -> None:
        """
        Extract RNA-Seq metadata from a Redmine issue
        """
        self._get_component()
        self._get_organism_abbrev()
        self._get_dataset_name()
        self._get_samples()
    
    def _get_dataset_name(self) -> None:
        name = self.custom["Internal dataset name"]
        if name:
            self.dataset_name = name
        else:
            self._add_error("Missing dataset name")

    def _get_samples(self) -> None:
        samples_str = self.custom["Sample Names"]
        if samples_str:
            samples = self._parse_samples(samples_str)
            if samples:
                self.samples = samples
            else:
                self._add_error("Wrong sample format")
        else:
            self._add_error("Missing samples")
    
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
            sample_names = dict()
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
                        raise SamplesParsingException(
                            f"Several samples have the same name '{sample_name}'")
                    else:
                        sample_names[sample_name] = True
                    
                    accessions_str = parts[1].strip()
                    accessions = [x.strip() for x in accessions_str.split(",")]
                    
                    if not self._validate_accessions(accessions):
                        if self._validate_accessions(sample_name.split(",")):
                            raise SamplesParsingException(
                                f"Sample name and accessions are switched? ({line})")
                        else:
                            raise SamplesParsingException(
                                f"Invalid accession among '{accessions}' ({line})")
                    
                    sample = {
                        "name": self._normalize_name(sample_name),
                        "accessions": accessions
                    }
                    samples.append(sample)
                else:
                    raise SamplesParsingException(f"Sample line doesn't have 2 parts ({line})")
        except SamplesParsingException as e:
            self._add_error(str(e))
        
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
            if not re.search(r'^[SE]R[RSXP]\d+$', acc):
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
        if re.search(r"[^A-Za-z0-9_.-]", name):
            print("WARNING: name contains special characters: %s (%s)" % (old_name, name))
            name = ""
        
        return name
