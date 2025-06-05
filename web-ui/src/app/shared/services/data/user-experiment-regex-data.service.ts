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
    const url = API_URL.USER_EXPERIMENT_PATTERN_PERMISSIONS.replace('${userName}', userName);
    return this.http.get<ExperimentRegexPermissionModel[]>(url);
  }

  addExperimentRegexPermissionToUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.USER_EXPERIMENT_PATTERN_PERMISSIONS.replace('${userName}', userName);
    return this.http.post(url, { regex, permission, priority });
  }

  updateExperimentRegexPermissionForUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number,
    id: string
  ): Observable<unknown> {
    const url = API_URL.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace(
      '${patternId}',
      id
    );
    return this.http.patch(url, { permission, priority, regex });
  }

  removeExperimentRegexPermissionFromUser(userName: string, id: string): Observable<unknown> {
    const url = API_URL.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace(
      '${patternId}',
      id
    );
    return this.http.delete(url);
  }
}
