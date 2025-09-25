# Updating GTFS-Dense Files

This guide explains how to update a `.gtfsd` file using the diff and patch feature. This feature allows you to efficiently update your GTFS data without having to download the entire feed every time.

## The Diff and Patch Process

The diff and patch process works as follows:

1.  You have an old `.gtfsd` file (e.g., `v1.gtfsd`).
2.  You have a new `.gtfsd` file (e.g., `v2.gtfsd`).
3.  You create a diff file (e.g., `v1_to_v2.gtfsd-diff`) that contains the differences between the two files.
4.  You can then distribute the small diff file to your users. Your application can then apply the diff file to the old `.gtfsd` file to get the new `.gtfsd` file.

## The Diff File (`.gtfsd-diff`)

The diff file is also a Protocol Buffers file. It contains a `FeedDiff` message that has lists of added, updated, and deleted entities.

### Header

The `FeedDiff` message has a header that contains the following fields:

*   `from_version`: The version of the old `.gtfsd` file.
*   `to_version`: The version of the new `.gtfsd` file.
*   `timestamp`: The timestamp of when the diff was created.
*   `checksum`: A SHA-256 checksum of the diff file's content. This is used to verify the integrity of the diff file before applying it.

## Creating a Diff

To create a diff, you need two `.gtfsd` files. The `gtfsdense.differ` module provides a `create_diff` function that will create a diff between two `TransitFeed` objects.

Conceptually, the differ works as follows:

1.  It compares the two feeds entity by entity (e.g., agencies, routes, stops).
2.  If an entity exists in the new feed but not in the old feed, it is added to the `added_*` list in the diff.
3.  If an entity exists in the old feed but not in the new feed, its index is added to the `deleted_*` list in the diff.
4.  If an entity exists in both feeds but has been modified, it is added to the `updated_*` list in the diff.

## Applying a Patch

To apply a patch, you need a `.gtfsd` file and a `.gtfsd-diff` file. The `gtfsdense.patcher` module provides an `apply_patch` function that will apply a diff to a `TransitFeed` object.

Conceptually, the patcher works as follows:

1.  It first verifies the checksum of the diff file to ensure that it has not been corrupted.
2.  It then verifies that the `from_version` in the diff matches the version of the base `.gtfsd` file.
3.  It then applies the changes in the diff to the base feed:
    *   It adds the entities from the `added_*` lists.
    *   It deletes the entities from the `deleted_*` lists.
    *   It updates the entities from the `updated_*` lists.
4.  Finally, it updates the header of the base feed to reflect the new version and timestamp.

## Conclusion

The diff and patch feature is a powerful tool for keeping your GTFS data up to date. It allows you to efficiently distribute updates to your users without requiring them to download the entire feed every time. This can save bandwidth and improve the user experience.
