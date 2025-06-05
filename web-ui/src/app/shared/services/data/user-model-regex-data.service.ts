import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { ModelRegexPermissionModel } from '../../interfaces/groups-data.interface';

@Injectable({
  providedIn: 'root',
})
export class UserModelRegexDataService {
  constructor(private readonly http: HttpClient) {}

  getModelRegexPermissionsForUser(userName: string): Observable<ModelRegexPermissionModel[]> {
    const url = API_URL.USER_REGISTERED_MODEL_PATTERN_PERMISSIONS.replace('${userName}', userName);
    return this.http.get<ModelRegexPermissionModel[]>(url);
  }

  addModelRegexPermissionToUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.USER_REGISTERED_MODEL_PATTERN_PERMISSIONS.replace('${userName}', userName);
    return this.http.post(url, { regex, permission, priority });
  }

  updateModelRegexPermissionForUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number,
    id: string
  ): Observable<unknown> {
    const url = API_URL.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace(
      '${patternId}',
      id
    );
    return this.http.patch(url, { regex, permission, priority });
  }

  removeModelRegexPermissionFromUser(userName: string, id: string): Observable<unknown> {
    const url = API_URL.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace(
      '${patternId}',
      id
    );
    return this.http.delete(url);
  }
}
