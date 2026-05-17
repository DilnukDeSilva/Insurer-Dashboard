export type Claim = {
  id: string;
  customer: string;
  policyId: string;
  vehicleModel: string;
  submittedDate: string;
  submittedTime: string;
  location: string;
  gpsMatched: boolean;
  timestampSigned: boolean;
  drunkTestAvailable: boolean;
  drivingLicenceAvailable: boolean;
  accidentImages: string[];
  thirdPartyApplicable: boolean;
};
