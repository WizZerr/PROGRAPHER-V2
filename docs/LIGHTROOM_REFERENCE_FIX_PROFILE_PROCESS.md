# Lightroom Reference Fix — Profile + Process Version

The first real Lightroom exercise exposed two useful contract bugs.

## 1. Process Version numbering

The XMP/internal value `11.0` is shown by Lightroom Classic as `Version 5`.

The reference verifier now compares the Lightroom UI label against the mapped
internal value instead of expecting the user to type `11.0`.

## 2. Adobe Color is not used as a literal CameraProfile field

The first fixture wrote:

`crs:CameraProfile="Adobe Color"`

Lightroom loaded the numeric edits, but displayed `Profile missing`.

For the transport/reference exercise we now use:

`crs:CameraProfile="Adobe Standard"`

This is a real base camera profile and gives us a clean, explicit profile value
to verify in the XMP round-trip.

The richer Adobe Color profile behavior can be modeled separately later rather
than pretending that the UI name is a direct DCP CameraProfile value.

## Important

Do not continue the old workspace created before this fix.
Prepare a fresh exercise after applying the patch.
