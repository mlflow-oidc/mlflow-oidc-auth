import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {
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
          models: this.http.get<RegisteredModelPermission[]>(
            API_URL.USER_REGISTERED_MODEL_PERMISSIONS.replace('${userName}', userName)
          ),
          experiments: this.http.get<ExperimentPermission[]>(
            API_URL.USER_EXPERIMENT_PERMISSIONS.replace('${userName}', userName)
          ),
          prompts: this.http.get<PromptPermission[]>(API_URL.USER_PROMPT_PERMISSIONS.replace('${userName}', userName)),
        }).pipe(
          map((response) => {
            user.models = response.models;
            user.experiments = response.experiments;
            user.prompts = response.prompts;
            return {
              user,
              models: response.models,
              experiments: response.experiments,
              prompts: response.prompts,
            };
          })
        );
      })
    );
  }

  getUserAccessKey(userName: string, expiration: Date) {
    return this.http.patch<TokenModel>(API_URL.CREATE_ACCESS_TOKEN, {
      username: userName,
      expiration: expiration,
    });
  }

  getAllUsers() {
    return this.http.get<string[]>(API_URL.ALL_USERS);
  }

  getAllServiceUsers() {
    return this.http.get<string[]>(`${API_URL.ALL_USERS}?service=true`);
  }

  createServiceAccount(body: UserModel) {
    return this.http.post<UserModel>(API_URL.CREATE_USER, body);
  }

  deleteUser(body: UserModel) {
    return this.http.delete<UserModel>(API_URL.DELETE_USER, { body });
  }
}
