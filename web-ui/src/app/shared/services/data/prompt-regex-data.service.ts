import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { API_URL } from 'src/app/core/configs/api-urls';
import { PromptRegexPermissionModel } from 'src/app/shared/interfaces/groups-data.interface';
@Injectable({
    providedIn: 'root',
})
export class PromptRegexDataService {
    constructor(private readonly http: HttpClient) { }

    getPromptRegexPermissionsForGroup(groupName: string) {
        return this.http.get<PromptRegexPermissionModel[]>(
            API_URL.GET_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName)
        );
    }

    addPromptRegexPermissionToGroup(
        groupName: string,
        regex: string,
        permission: string,
        priority: number
    ) {
        return this.http.post(
            API_URL.CREATE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName),
            {
                "regex": regex,
                "priority": priority,
                "permission": permission
            }
        );
    }

    updatePromptRegexPermissionForGroup(
        groupName: string,
        regex: string,
        permission: string,
        priority: number
    ) {
        return this.http.patch(
            API_URL.UPDATE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName),
            {
                "regex": regex,
                "priority": priority,
                "permission": permission
            }
        );
    }

    removePromptRegexPermissionFromGroup(
        groupName: string,
        regex: string
    ) {
        return this.http.delete(
            API_URL.DELETE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName),
            { body: { "regex": regex } }
        );
    }
}
