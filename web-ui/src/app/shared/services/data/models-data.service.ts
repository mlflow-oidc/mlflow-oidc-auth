import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import { ModelModel, ModelPermissionModel, ModelUserListModel } from '../../interfaces/models-data.interface';
import { API_URL } from 'src/app/core/configs/api-urls';

@Injectable({
  providedIn: 'root',
})
export class ModelsDataService {
  constructor(private readonly http: HttpClient) {}

  getAllModels() {
    return this.http.get<ModelModel[]>(API_URL.ALL_MODELS);
  }

  getModelsForUser(userName: string) {
    const url = API_URL.USER_REGISTERED_MODEL_PERMISSIONS.replace('${userName}', userName);
    return this.http.get<ModelPermissionModel[]>(url);
  }

  getUsersForModel(modelName: string) {
    const url = API_URL.REGISTERED_MODEL_USER_PERMISSIONS.replace('${modelName}', modelName);
    return this.http.get<ModelUserListModel[]>(url);
  }
}
