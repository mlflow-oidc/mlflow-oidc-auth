import { TestBed } from '@angular/core/testing';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { HttpClientModule } from '@angular/common/http';
import { ExperimentsDataService } from '../data/experiments-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { UserPermissionModel } from 'src/app/shared/interfaces/experiments-data.interface';
import { PermissionEnum, PermissionTypeEnum } from 'src/app/core/configs/permissions';

describe('ExperimentsDataService', () => {
  let service: ExperimentsDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientModule],
      providers: [provideHttpClientTesting(), ExperimentsDataService],
    });
    service = TestBed.inject(ExperimentsDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should fetch all experiments', () => {
    const mockExperiments = [
      {
        id: '1',
        name: 'Experiment 1',
        tags: {},
        permission: 'READ',
        type: 'TYPE_A',
      },
    ];
    service.getAllExperiments().subscribe((experiments) => {
      expect(experiments).toEqual(mockExperiments);
    });

    const req = httpMock.expectOne(API_URL.ALL_EXPERIMENTS);
    expect(req.request.method).toBe('GET');
    req.flush(mockExperiments);
  });

  it('should fetch experiments for a user', () => {
    const userName = 'testUser';

    const mockExperiments: UserPermissionModel[] = [
      {
        permission: PermissionEnum.MANAGE,
        username: 'experiment-manage-fallback',
      },
      {
        permission: PermissionEnum.MANAGE,
        username: 'experiment-manage-group',
      },
      {
        permission: PermissionEnum.MANAGE,
        username: 'experiment-manage-user',
      },
    ];
    const url = API_URL.USER_EXPERIMENT_PERMISSIONS.replace('${userName}', userName);

    service.getExperimentsForUser(userName).subscribe((experiments) => {
      expect(experiments).toEqual(mockExperiments);
    });

    const req = httpMock.expectOne(url);
    expect(req.request.method).toBe('GET');
    req.flush(mockExperiments);
  });

  it('should fetch users for an experiment', () => {
    const experimentId = 'testExperiment';
    const mockUsers: UserPermissionModel[] = [
      {
        permission: PermissionEnum.READ,
        username: 'bob@example.com',
      },
      {
        permission: PermissionEnum.MANAGE,
        username: 'alice@example.com',
      },
    ];
    const url = API_URL.EXPERIMENT_USER_PERMISSIONS.replace('${experimentId}', experimentId);

    service.getUsersForExperiment(experimentId).subscribe((users) => {
      expect(users).toEqual(mockUsers);
    });

    const req = httpMock.expectOne(url);
    expect(req.request.method).toBe('GET');
    req.flush(mockUsers);
  });
});
