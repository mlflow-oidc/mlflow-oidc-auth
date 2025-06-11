import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import {
  ExperimentModel,
  ExperimentForUserModel,
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
    return this.http.get<ExperimentForUserModel[]>(url);
  }

  getUsersForExperiment(experimentId: string) {
    const url = API_URL.EXPERIMENT_USER_PERMISSIONS.replace('${experimentId}', experimentId);
    return this.http.get<UserPermissionModel[]>(url);
  }
}
