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
"""VEuPathDB Redmine server parameters in one object."""


class VeupathParams:
    """Store basic parameters for the VEuPathDB Redmine server."""

    redmine_url = "https://redmine.apidb.org"
    project_id = 1976
    issues_fields = {
        "status": "status_name",
        "build": "fixed_version_id",
        # Custom fields
        "team": "cf_17",
        "datatype": "cf_94",
        "component": "cf_92",
        "organism_abbrev": "cf_110",
    }
