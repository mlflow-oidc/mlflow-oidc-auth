import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ModelsDataService } from '../data/models-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { ModelModel, ModelUserListModel } from 'src/app/shared/interfaces/models-data.interface';
import { PermissionEnum, PermissionTypeEnum } from 'src/app/core/configs/permissions';
import { Type } from '@angular/core';

describe('ModelsDataService', () => {
  let service: ModelsDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    });
    service = TestBed.inject(ModelsDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('getAllModels should perform GET to API_URL.ALL_MODELS', () => {
    const mockModels: ModelModel[] = [
      {
        name: 'model1',
        aliases: {},
        description: 'A test model',
        tags: {},
      },
    ];
    service.getAllModels().subscribe((models) => {
      expect(models).toEqual(mockModels);
    });
    const req = httpMock.expectOne(API_URL.ALL_MODELS);
    expect(req.request.method).toBe('GET');
    req.flush(mockModels);
  });

  it('getModelsForUser should perform GET to correct URL and map response', () => {
    const userName = 'john';
    const expectedUrl = API_URL.USER_REGISTERED_MODEL_PERMISSIONS.replace('${userName}', userName);
    const mockResponse = [
      {
        name: 'test1',
        permission: PermissionEnum.MANAGE,
        type: PermissionTypeEnum.USER,
      },
      {
        name: 'test2',
        permission: PermissionEnum.MANAGE,
        type: PermissionTypeEnum.USER,
      },
      {
        name: 'test3',
        permission: PermissionEnum.MANAGE,
        type: PermissionTypeEnum.FALLBACK,
      },
      {
        name: 'test4',
        permission: PermissionEnum.MANAGE,
        type: PermissionTypeEnum.FALLBACK,
      },
      {
        name: 'test5',
        permission: PermissionEnum.EDIT,
        type: PermissionTypeEnum.GROUP,
      },
    ];

    service.getModelsForUser(userName).subscribe((models) => {
      expect(models).toEqual(mockResponse);
    });
    const req = httpMock.expectOne(expectedUrl);
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('getUsersForModel should perform GET to correct URL', () => {
    const modelName = 'model1';
    const expectedUrl = API_URL.REGISTERED_MODEL_USER_PERMISSIONS.replace('${modelName}', modelName);
    const mockUsers: ModelUserListModel[] = [{ permission: PermissionEnum.EDIT, username: 'alex' }];

    service.getUsersForModel(modelName).subscribe((users) => {
      expect(users).toEqual(mockUsers);
    });
    const req = httpMock.expectOne(expectedUrl);
    expect(req.request.method).toBe('GET');
    req.flush(mockUsers);
  });
});
