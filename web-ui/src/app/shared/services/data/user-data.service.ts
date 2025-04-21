import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {
  AllUsersListModel,
  CurrentUserModel,
  TokenModel,
  RegisteredModelPermission,
  ExperimentPermission,
  PromptPermission,
  UserModel,
} from '../../interfaces/user-data.interface';
import { API_URL } from 'src/app/core/configs/api-urls';
import { switchMap, map } from 'rxjs/operators';
import { forkJoin, of } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class UserDataService {
  constructor(private readonly http: HttpClient) {}

  getCurrentUser() {
    return this.http.get<CurrentUserModel>(API_URL.GET_CURRENT_USER).pipe(
      switchMap((user) => {
        const userName = user.username;
        return forkJoin({
          user: of(user),
          models: this.http.get<{ models: RegisteredModelPermission[] }>(
            API_URL.MODELS_FOR_USER.replace('${userName}', userName)
          ),
          experiments: this.http.get<{ experiments: ExperimentPermission[] }>(
            API_URL.EXPERIMENTS_FOR_USER.replace('${userName}', userName)
          ),
          prompts: this.http.get<{ prompts: PromptPermission[] }>(
            API_URL.PROMPTS_FOR_USER.replace('${userName}', userName)
          ),
        }).pipe(
          map((response) => {
            user.models = response.models.models;
            user.experiments = response.experiments.experiments;
            user.prompts = response.prompts.prompts;
            return {
              user,
              models: response.models.models,
              experiments: response.experiments.experiments,
              prompts: response.prompts.prompts,
            };
          })
        );
      })
    );
  }

  getAccessKey() {
    return this.http.get<TokenModel>(API_URL.GET_ACCESS_TOKEN);
  }

  getUserAccessKey(userName: string) {
    return this.http.patch<TokenModel>(API_URL.GET_ACCESS_TOKEN, {
      username: userName,
    });
  }

  getAllUsers() {
    return this.http.get<AllUsersListModel>(API_URL.GET_ALL_USERS);
  }

  getAllServiceUsers() {
    return this.http.get<AllUsersListModel>(`${API_URL.GET_ALL_USERS}?service=true`);
  }

  createServiceAccount(body: UserModel) {
    return this.http.post<UserModel>(API_URL.CREATE_USER, body);
  }

  deleteUser(body: UserModel) {
    return this.http.delete<UserModel>(API_URL.DELETE_USER, { body });
  }
}
