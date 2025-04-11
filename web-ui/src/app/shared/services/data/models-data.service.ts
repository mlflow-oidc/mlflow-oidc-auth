import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { map } from "rxjs";

import {
  ModelModel,
  ModelPermissionsModel,
  ModelUserListModel,
} from "../../interfaces/models-data.interface";
import { API_URL } from "src/app/core/configs/api-urls";

@Injectable({
  providedIn: "root",
})
export class ModelsDataService {
  constructor(private readonly http: HttpClient) {}

  getAllModels() {
    return this.http.get<ModelModel[]>(API_URL.ALL_MODELS);
  }

  getModelsForUser(userName: string) {
    const url = API_URL.MODELS_FOR_USER.replace("${userName}", userName);
    return this.http
      .get<ModelPermissionsModel>(url)
      .pipe(map((response) => response.models));
  }

  getUsersForModel(modelName: string) {
    const url = API_URL.USERS_FOR_MODEL.replace("${modelName}", modelName);
    return this.http.get<ModelUserListModel[]>(url);
  }
}
