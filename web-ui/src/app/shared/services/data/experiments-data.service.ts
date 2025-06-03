import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map } from 'rxjs';

import {
  ExperimentModel,
  ExperimentsForUserModel,
  UserPermissionModel,
} from '../../interfaces/experiments-data.interface';
import { API_URL } from 'src/app/core/configs/api-urls';

@Injectable({
  providedIn: 'root',
})
export class ExperimentsDataService {
  constructor(private readonly http: HttpClient) {}

  getAllExperiments() {
    return this.http.get<ExperimentModel[]>(API_URL.ALL_EXPERIMENTS);
  }

  getExperimentsForUser(userName: string) {
    const url = API_URL.USER_EXPERIMENT_PERMISSIONS.replace('${userName}', userName);
    return this.http.get<ExperimentsForUserModel>(url).pipe(map(({ experiments }) => experiments));
  }

  getUsersForExperiment(experimentName: string) {
    const url = API_URL.USERS_FOR_EXPERIMENT.replace('${experimentName}', experimentName);
    return this.http.get<UserPermissionModel[]>(url);
  }
}
