// #315 default-on change, isolated for the lead's native verification/revert.
// To restore the former opt-in, replace true with FileExist of the profile
// acceptance/PoseCommand.enable marker. infected_poses.disable remains checked
// by HCRequestPose; caps, binds and settled-Move checks remain authoritative.
class HCPoseCommandAdmission
{
    static bool Enabled()
    {
        return true;
    }
}
