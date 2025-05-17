import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { PromptRegexPermissionModel } from '../../interfaces/groups-data.interface';

@Injectable({
  providedIn: 'root',
})
export class UserPromptRegexDataService {
  constructor(private readonly http: HttpClient) {}

  getPromptRegexPermissionsForUser(userName: string): Observable<PromptRegexPermissionModel[]> {
    const url = API_URL.GET_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.get<PromptRegexPermissionModel[]>(url);
  }

  addPromptRegexPermissionToUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.CREATE_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.post(url, { regex, permission, priority });
  }

  updatePromptRegexPermissionForUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.UPDATE_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.patch(url, { regex, permission, priority });
  }

  removePromptRegexPermissionFromUser(userName: string, regex: string): Observable<unknown> {
    const url = API_URL.DELETE_USER_PROMPT_REGEX_PERMISSION.replace('${userName}', userName);
    return this.http.delete(url, { body: { regex } });
  }
}
