import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { API_URL } from 'src/app/core/configs/api-urls';
import { ModelRegexPermissionModel } from 'src/app/shared/interfaces/groups-data.interface';
@Injectable({
  providedIn: 'root',
})
export class ModelRegexDataService {
  constructor(private readonly http: HttpClient) {}

  getModelRegexPermissionsForGroup(groupName: string) {
    return this.http.get<ModelRegexPermissionModel[]>(
      API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS.replace('${groupName}', groupName)
    );
  }

  addModelRegexPermissionToGroup(groupName: string, regex: string, permission: string, priority: number) {
    return this.http.post(API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS.replace('${groupName}', groupName), {
      regex: regex,
      priority: priority,
      permission: permission,
    });
  }

  updateModelRegexPermissionForGroup(
    groupName: string,
    regex: string,
    permission: string,
    priority: number,
    id: string
  ) {
    return this.http.patch(
      API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${patternId}',
        id
      ),
      {
        regex: regex,
        priority: priority,
        permission: permission,
      }
    );
  }

  removeModelRegexPermissionFromGroup(groupName: string, id: string) {
    return this.http.delete(
      API_URL.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${patternId}',
        id
      )
    );
  }
}
