import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { PermissionDataService } from './permission-data.service';
import {
  ExperimentPermissionRequestModel,
  ModelPermissionRequestModel,
} from 'src/app/shared/interfaces/permission-data.interface';
import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from '../../../core/configs/permissions';

describe('PermissionDataService', () => {
  let service: PermissionDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [PermissionDataService],
    });
    service = TestBed.inject(PermissionDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('Experiment Permission Methods', () => {
    describe('createExperimentPermission', () => {
      it('should create experiment permission for user with valid data', () => {
        const mockRequest: ExperimentPermissionRequestModel = {
          username: 'testuser',
          experiment_id: 'exp123',
          permission: PermissionEnum.READ
        };

        service.createExperimentPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${experimentId}', mockRequest.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ permission: mockRequest.permission });
        expect(req.request.responseType).toBe('text');
        req.flush('Success');
      });

      it('should handle special characters in username and experiment_id', () => {
        const mockRequest: ExperimentPermissionRequestModel = {
          username: 'test@user.com',
          experiment_id: 'exp-123_special',
          permission: PermissionEnum.MANAGE
        };

        service.createExperimentPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${experimentId}', mockRequest.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body).toEqual({ permission: mockRequest.permission });
        req.flush('Success');
      });

      it('should handle all permission types', () => {
        const permissions = [PermissionEnum.READ, PermissionEnum.EDIT, PermissionEnum.MANAGE, PermissionEnum.NO_PERMISSIONS];
        
        permissions.forEach((permission, index) => {
          const mockRequest: ExperimentPermissionRequestModel = {
            username: `user${index}`,
            experiment_id: `exp${index}`,
            permission: permission
          };

          service.createExperimentPermission(mockRequest).subscribe();

          const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
            .replace('${userName}', mockRequest.username)
            .replace('${experimentId}', mockRequest.experiment_id);
          const req = httpMock.expectOne(expectedUrl);
          expect(req.request.body.permission).toBe(permission);
          req.flush('Success');
        });
      });
    });

    describe('updateExperimentPermission', () => {
      it('should update experiment permission with valid data', () => {
        const mockRequest: ExperimentPermissionRequestModel = {
          username: 'updateuser',
          experiment_id: 'exp456',
          permission: PermissionEnum.EDIT
        };

        service.updateExperimentPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${experimentId}', mockRequest.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('PATCH');
        expect(req.request.body).toEqual({ permission: mockRequest.permission });
        expect(req.request.responseType).toBe('text');
        req.flush('Updated');
      });

      it('should handle empty username', () => {
        const mockRequest: ExperimentPermissionRequestModel = {
          username: '',
          experiment_id: 'exp456',
          permission: PermissionEnum.READ
        };

        service.updateExperimentPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${experimentId}', mockRequest.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(PermissionEnum.READ);
        req.flush('Updated');
      });
    });

    describe('deleteExperimentPermission', () => {
      it('should delete experiment permission with correct URL construction', () => {
        const mockRequest: ExperimentPermissionRequestModel = {
          username: 'deleteuser',
          experiment_id: 'exp789'
        };

        service.deleteExperimentPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${experimentId}', mockRequest.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('DELETE');
        req.flush('Deleted');
      });

      it('should handle URL encoding for special characters', () => {
        const mockRequest: ExperimentPermissionRequestModel = {
          username: 'user@example.com',
          experiment_id: 'exp-123_test'
        };

        service.deleteExperimentPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${experimentId}', mockRequest.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('DELETE');
        req.flush('Deleted');
      });

      it('should handle empty parameters', () => {
        const mockRequest: ExperimentPermissionRequestModel = {
          username: '',
          experiment_id: ''
        };

        service.deleteExperimentPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${experimentId}', mockRequest.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        req.flush('Deleted');
      });
    });
  });

  describe('Model Permission Methods', () => {
    describe('createModelPermission', () => {
      it('should create model permission with valid data', () => {
        const mockRequest: ModelPermissionRequestModel = {
          username: 'modeluser',
          name: 'testmodel',
          permission: PermissionEnum.READ
        };

        service.createModelPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_MODEL_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${modelName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ permission: mockRequest.permission });
        expect(req.request.responseType).toBe('json');
        req.flush('Success');
      });

      it('should handle complex model names', () => {
        const mockRequest: ModelPermissionRequestModel = {
          username: 'user1',
          name: 'my-awesome-model_v2.0',
          permission: PermissionEnum.MANAGE
        };

        service.createModelPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_MODEL_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${modelName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(PermissionEnum.MANAGE);
        req.flush('Success');
      });
    });

    describe('updateModelPermission', () => {
      it('should update model permission with valid data', () => {
        const mockRequest: ModelPermissionRequestModel = {
          username: 'updatemodeluser',
          name: 'updatemodel',
          permission: PermissionEnum.EDIT
        };

        service.updateModelPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_MODEL_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${modelName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('PATCH');
        expect(req.request.body).toEqual({ permission: mockRequest.permission });
        expect(req.request.responseType).toBe('json');
        req.flush('Updated');
      });

      it('should handle NO_PERMISSIONS enum', () => {
        const mockRequest: ModelPermissionRequestModel = {
          username: 'testuser',
          name: 'testmodel',
          permission: PermissionEnum.NO_PERMISSIONS
        };

        service.updateModelPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_MODEL_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${modelName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(PermissionEnum.NO_PERMISSIONS);
        req.flush('Updated');
      });
    });

    describe('deleteModelPermission', () => {
      it('should delete model permission with correct URL construction', () => {
        const mockRequest = {
          username: 'deletemodeluser',
          name: 'deletemodel'
        };

        service.deleteModelPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_MODEL_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${modelName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('DELETE');
        req.flush('Deleted');
      });

      it('should handle special characters in model name', () => {
        const mockRequest = {
          username: 'user',
          name: 'model-v1.0_final'
        };

        service.deleteModelPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_MODEL_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${modelName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        req.flush('Deleted');
      });
    });
  });

  describe('Prompt Permission Methods', () => {
    describe('createPromptPermission', () => {
      it('should create prompt permission with valid data', () => {
        const mockRequest = {
          username: 'promptuser',
          name: 'testprompt',
          permission: PermissionEnum.READ
        };

        service.createPromptPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_PROMPT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${promptName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ permission: mockRequest.permission });
        req.flush('Success');
      });

      it('should handle all permission types for prompts', () => {
        const permissions = [PermissionEnum.READ, PermissionEnum.EDIT, PermissionEnum.MANAGE];
        
        permissions.forEach((permission, index) => {
          const mockRequest = {
            username: `user${index}`,
            name: `prompt${index}`,
            permission: permission
          };

          service.createPromptPermission(mockRequest).subscribe();

          const expectedUrl = API_URL.USER_PROMPT_PERMISSION
            .replace('${userName}', mockRequest.username)
            .replace('${promptName}', mockRequest.name);
          const req = httpMock.expectOne(expectedUrl);
          expect(req.request.body.permission).toBe(permission);
          req.flush('Success');
        });
      });
    });

    describe('updatePromptPermission', () => {
      it('should update prompt permission with valid data', () => {
        const mockRequest = {
          username: 'updatepromptuser',
          name: 'updateprompt',
          permission: PermissionEnum.EDIT
        };

        service.updatePromptPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_PROMPT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${promptName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('PATCH');
        expect(req.request.body).toEqual({ permission: mockRequest.permission });
        req.flush('Updated');
      });

      it('should handle empty prompt name', () => {
        const mockRequest = {
          username: 'user',
          name: '',
          permission: PermissionEnum.READ
        };

        service.updatePromptPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_PROMPT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${promptName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(PermissionEnum.READ);
        req.flush('Updated');
      });
    });

    describe('deletePromptPermission', () => {
      it('should delete prompt permission with correct URL construction', () => {
        const mockRequest = {
          username: 'deletepromptuser',
          name: 'deleteprompt'
        };

        service.deletePromptPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_PROMPT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${promptName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('DELETE');
        req.flush('Deleted');
      });

      it('should handle special characters in prompt name', () => {
        const mockRequest = {
          username: 'user',
          name: 'my-prompt_v1.0'
        };

        service.deletePromptPermission(mockRequest).subscribe();

        const expectedUrl = API_URL.USER_PROMPT_PERMISSION
          .replace('${userName}', mockRequest.username)
          .replace('${promptName}', mockRequest.name);
        const req = httpMock.expectOne(expectedUrl);
        req.flush('Deleted');
      });
    });
  });

  describe('Group Experiment Permission Methods', () => {
    describe('addExperimentPermissionToGroup', () => {
      it('should add experiment permission to group with valid data', () => {
        const groupName = 'testgroup';
        const experimentId = 'exp123';
        const permission = PermissionEnum.READ;

        service.addExperimentPermissionToGroup(groupName, experimentId, permission).subscribe();

        const expectedUrl = API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${experimentId}', experimentId);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ permission: permission });
        req.flush('Success');
      });

      it('should handle group names with special characters', () => {
        const groupName = 'admin-group_v1';
        const experimentId = 'exp456';
        const permission = PermissionEnum.MANAGE;

        service.addExperimentPermissionToGroup(groupName, experimentId, permission).subscribe();

        const expectedUrl = API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${experimentId}', experimentId);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(permission);
        req.flush('Success');
      });
    });

    describe('removeExperimentPermissionFromGroup', () => {
      it('should remove experiment permission from group with correct URL', () => {
        const groupName = 'removegroup';
        const experimentId = 'exp789';

        service.removeExperimentPermissionFromGroup(groupName, experimentId).subscribe();

        const expectedUrl = API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${experimentId}', experimentId);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('DELETE');
        req.flush('Deleted');
      });

      it('should handle empty group name', () => {
        const groupName = '';
        const experimentId = 'exp123';

        service.removeExperimentPermissionFromGroup(groupName, experimentId).subscribe();

        const expectedUrl = API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${experimentId}', experimentId);
        const req = httpMock.expectOne(expectedUrl);
        req.flush('Deleted');
      });
    });

    describe('updateExperimentPermissionForGroup', () => {
      it('should update experiment permission for group with valid data', () => {
        const groupName = 'updategroup';
        const experimentId = 'exp456';
        const permission = PermissionEnum.EDIT;

        service.updateExperimentPermissionForGroup(groupName, experimentId, permission).subscribe();

        const expectedUrl = API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${experimentId}', experimentId);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('PATCH');
        expect(req.request.body).toEqual({ permission: permission });
        req.flush('Updated');
      });

      it('should handle all permission types for group experiments', () => {
        const permissions = [PermissionEnum.READ, PermissionEnum.EDIT, PermissionEnum.MANAGE, PermissionEnum.NO_PERMISSIONS];
        
        permissions.forEach((permission, index) => {
          const groupName = `group${index}`;
          const experimentId = `exp${index}`;

          service.updateExperimentPermissionForGroup(groupName, experimentId, permission).subscribe();

          const expectedUrl = API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL
            .replace('${groupName}', groupName)
            .replace('${experimentId}', experimentId);
          const req = httpMock.expectOne(expectedUrl);
          expect(req.request.body.permission).toBe(permission);
          req.flush('Updated');
        });
      });
    });
  });

  describe('Group Model Permission Methods', () => {
    describe('addModelPermissionToGroup', () => {
      it('should add model permission to group with valid data', () => {
        const modelName = 'testmodel';
        const groupName = 'modelgroup';
        const permission = PermissionEnum.READ;

        service.addModelPermissionToGroup(modelName, groupName, permission).subscribe();

        const expectedUrl = API_URL.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${modelName}', modelName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ permission: permission });
        req.flush('Success');
      });

      it('should handle complex model and group names', () => {
        const modelName = 'recommendation-engine_v2.1';
        const groupName = 'ml-team_production';
        const permission = PermissionEnum.MANAGE;

        service.addModelPermissionToGroup(modelName, groupName, permission).subscribe();

        const expectedUrl = API_URL.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${modelName}', modelName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(permission);
        req.flush('Success');
      });
    });

    describe('removeModelPermissionFromGroup', () => {
      it('should remove model permission from group with correct URL', () => {
        const modelName = 'removemodel';
        const groupName = 'removemodelgroup';

        service.removeModelPermissionFromGroup(modelName, groupName).subscribe();

        const expectedUrl = API_URL.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${modelName}', modelName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('DELETE');
        req.flush('Deleted');
      });
    });

    describe('updateModelPermissionForGroup', () => {
      it('should update model permission for group with valid data', () => {
        const modelName = 'updatemodel';
        const groupName = 'updatemodelgroup';
        const permission = PermissionEnum.EDIT;

        service.updateModelPermissionForGroup(modelName, groupName, permission).subscribe();

        const expectedUrl = API_URL.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${modelName}', modelName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('PATCH');
        expect(req.request.body).toEqual({ permission: permission });
        req.flush('Updated');
      });
    });
  });

  describe('Group Prompt Permission Methods', () => {
    describe('addPromptPermissionToGroup', () => {
      it('should add prompt permission to group with valid data', () => {
        const promptName = 'testprompt';
        const groupName = 'promptgroup';
        const permission = PermissionEnum.READ;

        service.addPromptPermissionToGroup(promptName, groupName, permission).subscribe();

        const expectedUrl = API_URL.GROUP_PROMPT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${promptName}', promptName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({ permission: permission });
        req.flush('Success');
      });

      it('should handle various permission levels', () => {
        const permissions = [PermissionEnum.READ, PermissionEnum.EDIT, PermissionEnum.MANAGE];
        
        permissions.forEach((permission, index) => {
          const promptName = `prompt${index}`;
          const groupName = `group${index}`;

          service.addPromptPermissionToGroup(promptName, groupName, permission).subscribe();

          const expectedUrl = API_URL.GROUP_PROMPT_PERMISSION_DETAIL
            .replace('${groupName}', groupName)
            .replace('${promptName}', promptName);
          const req = httpMock.expectOne(expectedUrl);
          expect(req.request.body.permission).toBe(permission);
          req.flush('Success');
        });
      });
    });

    describe('removePromptPermissionFromGroup', () => {
      it('should remove prompt permission from group with correct URL', () => {
        const promptName = 'removeprompt';
        const groupName = 'removepromptgroup';

        service.removePromptPermissionFromGroup(promptName, groupName).subscribe();

        const expectedUrl = API_URL.GROUP_PROMPT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${promptName}', promptName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('DELETE');
        req.flush('Deleted');
      });

      it('should handle URL encoding correctly', () => {
        const promptName = 'prompt@special';
        const groupName = 'group with spaces';

        service.removePromptPermissionFromGroup(promptName, groupName).subscribe();

        const expectedUrl = API_URL.GROUP_PROMPT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${promptName}', promptName);
        const req = httpMock.expectOne(expectedUrl);
        req.flush('Deleted');
      });
    });

    describe('updatePromptPermissionForGroup', () => {
      it('should update prompt permission for group with valid data', () => {
        const promptName = 'updateprompt';
        const groupName = 'updatepromptgroup';
        const permission = PermissionEnum.EDIT;

        service.updatePromptPermissionForGroup(promptName, groupName, permission).subscribe();

        const expectedUrl = API_URL.GROUP_PROMPT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${promptName}', promptName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.method).toBe('PATCH');
        expect(req.request.body).toEqual({ permission: permission });
        req.flush('Updated');
      });

      it('should handle NO_PERMISSIONS for group prompts', () => {
        const promptName = 'testprompt';
        const groupName = 'testgroup';
        const permission = PermissionEnum.NO_PERMISSIONS;

        service.updatePromptPermissionForGroup(promptName, groupName, permission).subscribe();

        const expectedUrl = API_URL.GROUP_PROMPT_PERMISSION_DETAIL
          .replace('${groupName}', groupName)
          .replace('${promptName}', promptName);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(PermissionEnum.NO_PERMISSIONS);
        req.flush('Updated');
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle HTTP errors for experiment permission creation', () => {
      const mockRequest: ExperimentPermissionRequestModel = {
        username: 'erroruser',
        experiment_id: 'exp123',
        permission: PermissionEnum.READ
      };

      service.createExperimentPermission(mockRequest).subscribe({
        next: () => fail('Expected error'),
        error: (error) => {
          expect(error.status).toBe(500);
        }
      });

      const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
        .replace('${userName}', mockRequest.username)
        .replace('${experimentId}', mockRequest.experiment_id);
      const req = httpMock.expectOne(expectedUrl);
      req.flush('Server Error', { status: 500, statusText: 'Internal Server Error' });
    });

    it('should handle HTTP errors for model permission updates', () => {
      const mockRequest: ModelPermissionRequestModel = {
        username: 'erroruser',
        name: 'errormodel',
        permission: PermissionEnum.EDIT
      };

      service.updateModelPermission(mockRequest).subscribe({
        next: () => fail('Expected error'),
        error: (error) => {
          expect(error.status).toBe(404);
        }
      });

      const expectedUrl = API_URL.USER_MODEL_PERMISSION
        .replace('${userName}', mockRequest.username)
        .replace('${modelName}', mockRequest.name);
      const req = httpMock.expectOne(expectedUrl);
      req.flush('Not Found', { status: 404, statusText: 'Not Found' });
    });

    it('should handle HTTP errors for group permission deletions', () => {
      service.removeExperimentPermissionFromGroup('errorgroup', 'errorexp').subscribe({
        next: () => fail('Expected error'),
        error: (error) => {
          expect(error.status).toBe(403);
        }
      });

      const expectedUrl = API_URL.GROUP_EXPERIMENT_PERMISSION_DETAIL
        .replace('${groupName}', 'errorgroup')
        .replace('${experimentId}', 'errorexp');
      const req = httpMock.expectOne(expectedUrl);
      req.flush('Forbidden', { status: 403, statusText: 'Forbidden' });
    });
  });

  describe('Edge Cases', () => {
    it('should handle null and undefined values gracefully', () => {
      // Test with null username
      const mockRequest: ExperimentPermissionRequestModel = {
        username: null as any,
        experiment_id: 'exp123',
        permission: PermissionEnum.READ
      };

      service.createExperimentPermission(mockRequest).subscribe();

      const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
        .replace('${userName}', mockRequest.username)
        .replace('${experimentId}', mockRequest.experiment_id);
      const req = httpMock.expectOne(expectedUrl);
      expect(req.request.body.permission).toBe(PermissionEnum.READ);
      req.flush('Success');
    });

    it('should handle very long strings', () => {
      const longString = 'a'.repeat(1000);
      const mockRequest: ModelPermissionRequestModel = {
        username: longString,
        name: longString,
        permission: PermissionEnum.MANAGE
      };

      service.createModelPermission(mockRequest).subscribe();

      const expectedUrl = API_URL.USER_MODEL_PERMISSION
        .replace('${userName}', mockRequest.username)
        .replace('${modelName}', mockRequest.name);
      const req = httpMock.expectOne(expectedUrl);
      expect(req.request.body.permission).toBe(PermissionEnum.MANAGE);
      req.flush('Success');
    });

    it('should handle concurrent requests', () => {
      const requests = [
        { username: 'user1', experiment_id: 'exp1', permission: PermissionEnum.READ },
        { username: 'user2', experiment_id: 'exp2', permission: PermissionEnum.EDIT },
        { username: 'user3', experiment_id: 'exp3', permission: PermissionEnum.MANAGE }
      ];

      requests.forEach((request, index) => {
        service.createExperimentPermission(request).subscribe();
      });

      requests.forEach((request, index) => {
        const expectedUrl = API_URL.USER_EXPERIMENT_PERMISSION
          .replace('${userName}', request.username)
          .replace('${experimentId}', request.experiment_id);
        const req = httpMock.expectOne(expectedUrl);
        expect(req.request.body.permission).toBe(request.permission);
        req.flush(`Success ${index}`);
      });
    });
  });

  describe('Service Dependency Injection', () => {
    it('should inject HttpClient properly', () => {
      expect(service['http']).toBeDefined();
    });

    it('should have all required methods', () => {
      const expectedMethods = [
        'createExperimentPermission',
        'updateExperimentPermission',
        'deleteExperimentPermission',
        'createModelPermission',
        'updateModelPermission',
        'deleteModelPermission',
        'createPromptPermission',
        'updatePromptPermission',
        'deletePromptPermission',
        'addExperimentPermissionToGroup',
        'removeExperimentPermissionFromGroup',
        'updateExperimentPermissionForGroup',
        'addModelPermissionToGroup',
        'removeModelPermissionFromGroup',
        'updateModelPermissionForGroup',
        'addPromptPermissionToGroup',
        'removePromptPermissionFromGroup',
        'updatePromptPermissionForGroup'
      ];

      expectedMethods.forEach(method => {
        expect(typeof (service as any)[method]).toBe('function');
      });
    });
  });
});