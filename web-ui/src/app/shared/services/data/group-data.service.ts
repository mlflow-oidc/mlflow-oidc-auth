import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import { API_URL } from 'src/app/core/configs/api-urls';
import { ExperimentModel, ModelModel } from 'src/app/shared/interfaces/groups-data.interface';

@Injectable({
  providedIn: 'root',
})
export class GroupDataService {
  constructor(private readonly http: HttpClient) {}

  getAllGroups() {
    return this.http.get<string[]>(API_URL.ALL_GROUPS);
  }

  getAllExperimentsForGroup(groupName: string) {
    return this.http.get<ExperimentModel[]>(API_URL.GROUP_EXPERIMENT_PERMISSIONS.replace('${groupName}', groupName));
  }

  getAllRegisteredModelsForGroup(groupName: string) {
    return this.http.get<ModelModel[]>(API_URL.GROUP_REGISTERED_MODEL_PERMISSIONS.replace('${groupName}', groupName));
  }

  getAllPromptsForGroup(groupName: string) {
    return this.http.get<ModelModel[]>(API_URL.GROUP_PROMPT_PERMISSIONS.replace('${groupName}', groupName));
  }
}
