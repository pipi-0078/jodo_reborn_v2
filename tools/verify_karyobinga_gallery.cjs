// Backward-compatible entry point; now verifies both approved variants.
process.env.KARYOBINGA_BASE ||= process.env.GALLERY_BASE;
require('./verify-karyobinga-pair.cjs');
