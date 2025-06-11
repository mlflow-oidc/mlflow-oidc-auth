import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map } from 'rxjs';

import { PromptModel, PromptPermissionModel, PromptUserListModel } from '../../interfaces/prompts-data.interface';
import { API_URL } from 'src/app/core/configs/api-urls';

@Injectable({
  providedIn: 'root',
})
export class PromptsDataService {
  constructor(private readonly http: HttpClient) {}

  getAllPrompts() {
    return this.http.get<PromptModel[]>(API_URL.ALL_PROMPTS);
  }

  getPromptsForUser(userName: string) {
    const url = API_URL.USER_PROMPT_PERMISSIONS.replace('${userName}', userName);
    return this.http.get<PromptPermissionModel[]>(url);
  }

  getUsersForPrompt(promptName: string) {
    const url = API_URL.PROMPT_USER_PERMISSIONS.replace('${promptName}', promptName);
    return this.http.get<PromptUserListModel[]>(url);
  }
}
