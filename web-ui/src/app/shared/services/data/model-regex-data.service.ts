import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { API_URL } from 'src/app/core/configs/api-urls';
import { ModelRegexPermissionModel } from 'src/app/shared/interfaces/groups-data.interface';
@Injectable({
  providedIn: 'root',
})
export class ModelRegexDataService {
  constructor(private readonly http: HttpClient) { }

  getModelRegexPermissionsForGroup(groupName: string) {
    return this.http.get<ModelRegexPermissionModel[]>(
      API_URL.GET_GROUP_REGISTERED_MODEL_REGEX_PERMISSION.replace('${groupName}', groupName)
    );
  }

  addModelRegexPermissionToGroup(
    groupName: string,
    pattern: string,
    permission: string
  ) {
    return this.http.post(
      API_URL.CREATE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION.replace('${groupName}', groupName),
      { pattern, permission }
    );
  }

  updateModelRegexPermissionForGroup(
    groupName: string,
    regexPermissionId: string,
    pattern: string,
    permission: string
  ) {
    return this.http.patch(
      API_URL.UPDATE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION.replace('${groupName}', groupName),
      { id: regexPermissionId, pattern, permission }
    );
  }

  removeModelRegexPermissionFromGroup(
    groupName: string,
    regexPermissionId: string
  ) {
    return this.http.delete(
      API_URL.DELETE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION.replace('${groupName}', groupName),
      { body: { id: regexPermissionId } }
    );
  }

}
