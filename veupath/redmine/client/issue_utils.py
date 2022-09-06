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


from redminelib import exceptions


class IssueUtils:
    max_title = 60
    max_title_full = 100

    @staticmethod
    def get_custom_fields(issue) -> dict:
        """
        Put all Redmine custom fields in a dict instead of an array
        Return a dict where the value is the value of the field
        """
        
        cfs = {}
        for c in issue.custom_fields:
            try:
                cfs[c["name"]] = c["value"]
            except exceptions.ResourceAttrError:
                pass
        return cfs

    @staticmethod
    def get_custom_ids(issue) -> dict:
        """
        Put all Redmine custom fields in a dict instead of an array
        Return a dict where the value is the id of the field
        """
        
        cfs = {}
        try:
            for c in issue.custom_fields:
                cfs[c["name"]] = c["id"]
        except exceptions.ResourceAttrError:
            pass
        return cfs
    
    @staticmethod
    def tostr(issue) -> str:
        max_title = IssueUtils.max_title
        title = issue.subject
        if len(title) > max_title:
            title = title[0:max_title] + "..."
        return f"{issue.id} ({title})"

    @staticmethod
    def tostr_full(issue) -> str:
        max_title = IssueUtils.max_title_full
        title = issue.subject
        if len(title) > max_title:
            title = title[0:max_title] + "..."
        
        cfs = IssueUtils.get_custom_fields(issue)

        build = "(no build)"
        team = "(no team)"
        component = "(no component)"
        assignee = "(no assignee)"
        datatype = "(no datatype)"

        try:
            if cfs["VEuPathDB Team"]:
                team = cfs["VEuPathDB Team"]
        except KeyError:
            pass

        try:
            component = ",".join(cfs["Component DB"])
        except KeyError:
            pass

        try:
            if cfs["DataType"]:
                datatype = cfs["DataType"]
        except KeyError:
            pass

        try:
            assignee = issue.assigned_to["name"]
            build = issue.fixed_version
        except exceptions.ResourceAttrError:
            pass

        return f"{assignee}\t{team}\t{build}\t{component}\t'{datatype}'\t{issue.id}\t({title})"

    @staticmethod
    def print_issues(issues: list, description: str) -> None:
        print(f"{len(issues)} issues for {description}")
        for issue in issues:
            print(IssueUtils.tostr_full(issue))
