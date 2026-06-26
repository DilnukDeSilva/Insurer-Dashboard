export type Claim = {
  nic: string;
  customer: string;
  policyId: string;
  vehicleModel: string;
  submittedDate: string;
  submittedTime: string;
  location: string;
  gpsMatched: boolean;
  timestampSigned: boolean;
  userVerificationAvailable: boolean;
  thirdPartyApplicable: boolean;
  accidentImages: string[];
  userVerificationPhotos: string[];
  thirdPartyPhotos: string[];
};
