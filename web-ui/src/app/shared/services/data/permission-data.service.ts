import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {
  ExperimentPermissionRequestModel,
  ModelPermissionRequestModel,
} from 'src/app/shared/interfaces/permission-data.interface';
import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from '../../../core/configs/permissions';

@Injectable({
  providedIn: 'root',
})
export class PermissionDataService {
  constructor(private readonly http: HttpClient) {}

  createExperimentPermission(input: ExperimentPermissionRequestModel) {
    const url = API_URL.USER_EXPERIMENT_PERMISSION.replace('${userName}', input.username).replace(
      '${experimentId}',
      input.experiment_id
    );
    return this.http.post(
      url,
      { permission: input.permission },
      {
        responseType: 'text',
      }
    );
  }

  updateExperimentPermission(input: ExperimentPermissionRequestModel) {
    const url = API_URL.USER_EXPERIMENT_PERMISSION.replace('${userName}', input.username).replace(
      '${experimentId}',
      input.experiment_id
    );
    return this.http.patch(
      url,
      { permission: input.permission },
      {
        responseType: 'text',
      }
    );
  }

  deleteExperimentPermission(input: ExperimentPermissionRequestModel) {
    const url = API_URL.USER_EXPERIMENT_PERMISSION.replace('${userName}', input.username).replace(
      '${experimentId}',
      input.experiment_id
    );
    return this.http.delete(url);
  }

  createModelPermission(input: ModelPermissionRequestModel) {
    const url = API_URL.USER_MODEL_PERMISSION.replace('${userName}', input.username).replace(
      '${modelName}',
      input.name
    );
    return this.http.post(
      url,
      { permission: input.permission },
      {
        responseType: 'json',
      }
    );
  }

  updateModelPermission(input: ModelPermissionRequestModel) {
    const url = API_URL.USER_MODEL_PERMISSION.replace('${userName}', input.username).replace(
      '${modelName}',
      input.name
    );
    return this.http.patch(
      url,
      { permission: input.permission },
      {
        responseType: 'json',
      }
    );
  }

  deleteModelPermission(input: { name: string; username: string }) {
    const url = API_URL.USER_MODEL_PERMISSION.replace('${userName}', input.username).replace(
      '${modelName}',
      input.name
    );
    return this.http.delete(url);
  }

  createPromptPermission(body: { name: string; username: string; permission: string }) {
    const url = API_URL.USER_PROMPT_PERMISSION.replace('${userName}', body.username).replace(
      '${promptName}',
      body.name
    );
    return this.http.post(url, { permission: body.permission });
  }

  updatePromptPermission(body: { name: string; username: string; permission: string }) {
    const url = API_URL.USER_PROMPT_PERMISSION.replace('${userName}', body.username).replace(
      '${promptName}',
      body.name
    );
    return this.http.patch(url, { permission: body.permission });
  }

  deletePromptPermission(body: { name: string; username: string }) {
    const url = API_URL.USER_PROMPT_PERMISSION.replace('${userName}', body.username).replace(
      '${promptName}',
      body.name
    );
    return this.http.delete(url);
  }

  addExperimentPermissionToGroup(groupName: string, experiment_id: string, permission: PermissionEnum) {
    return this.http.post(
      API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${experimentId}',
        experiment_id
      ),
      {
        permission,
      }
    );
  }

  addModelPermissionToGroup(modelName: string, groupName: string, permission: string) {
    return this.http.post(
      API_URL.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${modelName}',
        modelName
      ),
      {
        permission,
      }
    );
  }

  addPromptPermissionToGroup(promptName: string, groupName: string, permission: string) {
    return this.http.post(
      API_URL.GROUP_PROMPT_PERMISSION_DETAIL.replace('${groupName}', groupName).replace('${promptName}', promptName),
      {
        permission,
      }
    );
  }

  removeExperimentPermissionFromGroup(groupName: string, experiment_id: string) {
    return this.http.delete(
      API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${experimentId}',
        experiment_id
      )
    );
  }

  removeModelPermissionFromGroup(modelName: string, groupName: string) {
    return this.http.delete(
      API_URL.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${modelName}',
        modelName
      )
    );
  }

  removePromptPermissionFromGroup(promptName: string, groupName: string) {
    return this.http.delete(
      API_URL.GROUP_PROMPT_PERMISSION_DETAIL.replace('${groupName}', groupName).replace('${promptName}', promptName)
    );
  }

  updateExperimentPermissionForGroup(groupName: string, experiment_id: string, permission: string) {
    return this.http.patch(
      API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${experimentId}',
        experiment_id
      ),
      {
        permission,
      }
    );
  }

  updateModelPermissionForGroup(modelName: string, groupName: string, permission: string) {
    return this.http.patch(
      API_URL.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL.replace('${groupName}', groupName).replace(
        '${modelName}',
        modelName
      ),
      {
        permission,
      }
    );
  }

  updatePromptPermissionForGroup(promptName: string, groupName: string, permission: string) {
    return this.http.patch(
      API_URL.GROUP_PROMPT_PERMISSION_DETAIL.replace('${groupName}', groupName).replace('${promptName}', promptName),
      {
        permission,
      }
    );
  }
}
