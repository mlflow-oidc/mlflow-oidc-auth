import { TestBed } from '@angular/core/testing';
import { HttpClientModule } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { GroupDataService } from '../data/group-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { GroupsDataModel, ExperimentModel, ModelModel } from 'src/app/shared/interfaces/groups-data.interface';
import { PermissionEnum } from 'src/app/core/configs/permissions';

describe('GroupDataService', () => {
  let service: GroupDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientModule],
      providers: [GroupDataService, provideHttpClientTesting()],
    });
    service = TestBed.inject(GroupDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch all groups', () => {
    const mockResponse: GroupsDataModel = { groups: ['group1', 'group2'] };

    service.getAllGroups().subscribe((response) => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.ALL_GROUPS);
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('should fetch all experiments for a group', () => {
    const groupName = 'test-group';
    const mockResponse: ExperimentModel[] = [
      { id: 'exp1', name: 'Experiment 1', permission: PermissionEnum.READ },
      { id: 'exp1', name: 'Experiment 1', permission: PermissionEnum.EDIT },
      { id: 'exp2', name: 'Experiment 2', permission: PermissionEnum.MANAGE },
      {
        id: 'exp3',
        name: 'Experiment 3',
        permission: PermissionEnum.NO_PERMISSIONS,
      },
    ];

    service.getAllExperimentsForGroup(groupName).subscribe((response) => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.EXPERIMENTS_FOR_GROUP.replace('${groupName}', groupName));
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('should fetch all registered models for a group', () => {
    const groupName = 'test-group';
    const mockResponse: ModelModel[] = [
      { name: 'Model 1', permission: PermissionEnum.READ },
      { name: 'Model 2', permission: PermissionEnum.EDIT },
      { name: 'Model 3', permission: PermissionEnum.MANAGE },
      { name: 'Model 4', permission: PermissionEnum.NO_PERMISSIONS },
    ];

    service.getAllRegisteredModelsForGroup(groupName).subscribe((response) => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.MODELS_FOR_GROUP.replace('${groupName}', groupName));
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('should fetch all prompts for a group', () => {
    const groupName = 'test-group';
    const mockResponse: ModelModel[] = [
      { name: 'Prompt 1', permission: PermissionEnum.READ },
      { name: 'Prompt 2', permission: PermissionEnum.EDIT },
      { name: 'Prompt 3', permission: PermissionEnum.MANAGE },
      { name: 'Prompt 4', permission: PermissionEnum.NO_PERMISSIONS },
    ];

    service.getAllPromptsForGroup(groupName).subscribe((response) => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.PROMPTS_FOR_GROUP.replace('${groupName}', groupName));
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });
});
