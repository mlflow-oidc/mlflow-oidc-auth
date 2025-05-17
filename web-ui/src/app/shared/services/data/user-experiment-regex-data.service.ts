import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { ExperimentRegexPermissionModel } from '../../interfaces/groups-data.interface';

@Injectable({
  providedIn: 'root',
})
export class UserExperimentRegexDataService {
  constructor(private readonly http: HttpClient) {}

  getExperimentRegexPermissionsForUser(userName: string): Observable<ExperimentRegexPermissionModel[]> {
    const url = API_URL.GET_USER_EXPERIMENT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.get<ExperimentRegexPermissionModel[]>(url);
  }

  addExperimentRegexPermissionToUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.CREATE_USER_EXPERIMENT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.post(url, { regex, permission, priority });
  }

  updateExperimentRegexPermissionForUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.UPDATE_USER_EXPERIMENT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.patch(url, { regex, permission, priority });
  }

  removeExperimentRegexPermissionFromUser(userName: string, regex: string): Observable<unknown> {
    const url = API_URL.DELETE_USER_EXPERIMENT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.delete(url, { body: { regex } });
  }
}
