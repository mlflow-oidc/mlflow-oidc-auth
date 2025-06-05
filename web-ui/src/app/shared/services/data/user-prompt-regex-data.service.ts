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
    const url = API_URL.USER_PROMPT_PATTERN_PERMISSIONS.replace('${userName}', userName);
    return this.http.get<PromptRegexPermissionModel[]>(url);
  }

  addPromptRegexPermissionToUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number
  ): Observable<unknown> {
    const url = API_URL.USER_PROMPT_PATTERN_PERMISSIONS.replace('${userName}', userName);
    return this.http.post(url, { regex, permission, priority });
  }

  updatePromptRegexPermissionForUser(
    userName: string,
    regex: string,
    permission: PermissionEnum,
    priority: number,
    id: string
  ): Observable<unknown> {
    const url = API_URL.USER_PROMPT_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace(
      '${patternId}',
      id
    );
    return this.http.patch(url, { regex, permission, priority });
  }

  removePromptRegexPermissionFromUser(userName: string, id: string): Observable<unknown> {
    const url = API_URL.USER_PROMPT_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace(
      '${patternId}',
      id
    );
    return this.http.delete(url);
  }
}
