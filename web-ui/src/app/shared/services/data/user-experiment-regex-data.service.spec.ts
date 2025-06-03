import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { UserExperimentRegexDataService } from './user-experiment-regex-data.service';
import { API_URL } from 'src/app/core/configs/api-urls';
import { PermissionEnum } from 'src/app/core/configs/permissions';
import { ExperimentRegexPermissionModel } from '../../interfaces/groups-data.interface';

describe('UserExperimentRegexDataService', () => {
  let service: UserExperimentRegexDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [UserExperimentRegexDataService],
    });
    service = TestBed.inject(UserExperimentRegexDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch experiment regex permissions for user', () => {
    const userName = 'user1';
    const mockData: ExperimentRegexPermissionModel[] = [
      { id: '1', group_id: 'group1', regex: '^abc', permission: PermissionEnum.READ, priority: 1 },
    ];
    service.getExperimentRegexPermissionsForUser(userName).subscribe((data) => {
      expect(data).toEqual(mockData);
    });
    const req = httpMock.expectOne(API_URL.USER_EXPERIMENT_PATTERN_PERMISSIONS.replace('${userName}', userName));
    expect(req.request.method).toBe('GET');
    req.flush(mockData);
  });

  it('should add experiment regex permission to user', () => {
    const userName = 'user1';
    const regex = '.*';
    const permission = PermissionEnum.EDIT;
    const priority = 2;
    service.addExperimentRegexPermissionToUser(userName, regex, permission, priority).subscribe((resp) => {
      expect(resp).toEqual({});
    });
    const req = httpMock.expectOne(API_URL.USER_EXPERIMENT_PATTERN_PERMISSIONS.replace('${userName}', userName));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush({});
  });

  it('should update experiment regex permission for user', () => {
    const userName = 'user1';
    const regex = '^test$';
    const permission = PermissionEnum.EDIT;
    const priority = 3;
    const id = '1';
    service.updateExperimentRegexPermissionForUser(userName, regex, permission, priority, id).subscribe((resp) => {
      expect(resp).toEqual({ updated: true });
    });
    const req = httpMock.expectOne(
      API_URL.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace('${patternId}', id)
    );
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ regex, permission, priority });
    req.flush({ updated: true });
  });

  it('should remove experiment regex permission from user', () => {
    const userName = 'user1';
    const id = '1';
    service.removeExperimentRegexPermissionFromUser(userName, id).subscribe((resp) => {
      expect(resp).toEqual({ deleted: true });
    });
    const req = httpMock.expectOne(
      API_URL.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL.replace('${userName}', userName).replace('${patternId}', id)
    );
    expect(req.request.method).toBe('DELETE');
    req.flush({ deleted: true });
  });
});
