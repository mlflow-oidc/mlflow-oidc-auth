import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { API_URL } from 'src/app/core/configs/api-urls';
import { ExperimentRegexPermissionModel } from 'src/app/shared/interfaces/groups-data.interface';
@Injectable({
  providedIn: 'root',
})
export class ExperimentRegexDataService {
  constructor(private readonly http: HttpClient) { }

  getExperimentRegexPermissionsForGroup(groupName: string) {
    return this.http.get<ExperimentRegexPermissionModel[]>(
      API_URL.GET_GROUP_EXPERIMENT_REGEX_PERMISSION.replace('${groupName}', groupName)
    );
  }

  addExperimentRegexPermissionToGroup(
    groupName: string,
    pattern: string,
    permission: string
  ) {
    return this.http.post(
      API_URL.CREATE_GROUP_EXPERIMENT_REGEX_PERMISSION.replace('${groupName}', groupName),
      { pattern, permission }
    );
  }

  updateExperimentRegexPermissionForGroup(
    groupName: string,
    regexPermissionId: string,
    pattern: string,
    permission: string
  ) {
    return this.http.patch(
      API_URL.UPDATE_GROUP_EXPERIMENT_REGEX_PERMISSION.replace('${groupName}', groupName),
      { id: regexPermissionId, pattern, permission }
    );
  }

  removeExperimentRegexPermissionFromGroup(
    groupName: string,
    regexPermissionId: string
  ) {
    return this.http.delete(
      API_URL.DELETE_GROUP_EXPERIMENT_REGEX_PERMISSION.replace('${groupName}', groupName),
      { body: { id: regexPermissionId } }
    );
  }

}
