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
        pattern: string,
        permission: string
    ) {
        return this.http.post(
            API_URL.CREATE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName),
            { pattern, permission }
        );
    }

    updatePromptRegexPermissionForGroup(
        groupName: string,
        regexPermissionId: string,
        pattern: string,
        permission: string
    ) {
        return this.http.patch(
            API_URL.UPDATE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName),
            { id: regexPermissionId, pattern, permission }
        );
    }

    removePromptRegexPermissionFromGroup(
        groupName: string,
        regexPermissionId: string
    ) {
        return this.http.delete(
            API_URL.DELETE_GROUP_PROMPT_REGEX_PERMISSION.replace('${groupName}', groupName),
            { body: { id: regexPermissionId } }
        );
    }
}
