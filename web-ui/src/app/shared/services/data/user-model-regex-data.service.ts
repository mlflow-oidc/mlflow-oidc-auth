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
    const url = API_URL.GET_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.get<ModelRegexPermissionModel[]>(url);
  }

  addModelRegexPermissionToUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.CREATE_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.post(url, { regex, permission, priority });
  }

  updateModelRegexPermissionForUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.UPDATE_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.patch(url, { regex, permission, priority });
  }

  removeModelRegexPermissionFromUser(userName: string, regex: string): Observable<unknown> {
    const url = API_URL.DELETE_USER_REGISTERED_MODEL_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.delete(url, { body: { regex } });
  }
}
