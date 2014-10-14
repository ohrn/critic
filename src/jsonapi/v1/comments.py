# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import api
import jsonapi

@jsonapi.PrimaryResource
class Comments(object):
    """Issues and notes in reviews."""

    name = "comments"
    contexts = (None, "reviews")
    value_class = (api.comment.Comment, api.comment.Issue, api.comment.Note)
    exceptions = (api.comment.CommentError, api.reply.ReplyError)

    @staticmethod
    def json(value, parameters):
        """{
             "id": integer,
             "type": "issue" or "note",
             "is_draft": boolean,
             "state": "open", "addressed" or "resolved" (null for notes),
             "review": integer,
             "author": integer,
             "location": Location or null,
             "resolved_by": integer, // user that resolved the issue
             "addressed_by": integer, // commit that addressed the issue
             "timestamp": float,
             "text": string,
             "replies": integer[],
           }

           Location {
             "type": "commit-message" or "file-version",
             "first_line": integer, // first commented line (one-based, inclusive)
             "last_line": integer, // last commented line (one-based, inclusive)
           }

           CommitMessageLocation : Location {
             "commit": integer // commented commit
           }

           FileVersionLocation : Location {
             "file": integer, // commented file
             "changeset": integer or null, // commented changeset
             "commit": integer, // commented commit
           }"""

        if isinstance(value, api.comment.Issue):
            state = value.state
            resolved_by = value.resolved_by
            addressed_by = value.addressed_by
        else:
            state = None
            resolved_by = None
            addressed_by = None

        if value.location:
            location = value.location

            if location.type == "file-version":
                changeset = jsonapi.deduce("v1/changesets", parameters)

                if not changeset:
                    # FileVersionLocation.translateTo() only allows one, so let
                    # a deduced changeset win over a deduced commit.
                    commit = jsonapi.deduce("v1/commits", parameters)
                else:
                    commit = None

                if changeset or commit:
                    location = location.translateTo(changeset=changeset,
                                                    commit=commit)

                    if not location:
                        raise jsonapi.ResourceSkipped(
                            "Comment not present in changeset/commit")

            location_json = {
                "type": location.type,
                "first_line": location.first_line,
                "last_line": location.last_line
            }

            if location.type == "commit-message":
                location_json.update({
                    "commit": location.commit
                })
            else:
                location_json.update({
                    "file": location.file,
                    "changeset": location.changeset,
                    "side": location.side,
                    "commit": location.commit,
                    "is_translated": location.is_translated
                })
        else:
            location_json = None

        timestamp = jsonapi.v1.timestamp(value.timestamp)
        return parameters.filtered(
            "comments", { "id": value.id,
                          "type": value.type,
                          "is_draft": value.is_draft,
                          "state": state,
                          "review": value.review,
                          "author": value.author,
                          "location": location_json,
                          "resolved_by": resolved_by,
                          "addressed_by": addressed_by,
                          "timestamp": timestamp,
                          "text": value.text,
                          "replies": value.replies })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) comments in reviews.

           COMMENT_ID : integer

           Retrieve a comment identified by its unique numeric id."""

        comment = api.comment.fetch(
            parameters.critic, comment_id=jsonapi.numeric_id(argument))

        review = jsonapi.deduce("v1/reviews", parameters)
        if review and review != comment.review:
            raise jsonapi.PathError(
                "Comment does not belong to specified review")

        return Comments.setAsContext(parameters, comment)

    @staticmethod
    def multiple(parameters):
        """Retrieve all comments in the system (or review.)

           with_reply : REPLY_ID : integer

           Retrieve only the comment to which the specified reply is a reply.
           This is equivalent to accessing /api/v1/comments/COMMENT_ID with that
           comment's numeric id.  When used, any other parameters are ignored.

           review : REVIEW_ID : integer

           Retrieve only comments in the specified review.  Can only be used if
           a review is not specified in the resource path.

           author : AUTHOR : integer or string

           Retrieve only comments authored by the specified user, identified by
           the user's unique numeric id or user name.

           comment_type : TYPE : -

           Retrieve only comments of the specified type.  Valid values are:
           <code>issue</code> and <code>note</code>.

           state : STATE : -

           Retrieve only issues in the specified state.  Valid values are:
           <code>open</code>, <code>addressed</code> and <code>resolved</code>.

           location_type : LOCATION : -

           Retrieve only comments in the specified type of location.  Valid
           values are: <code>general</code>, <code>commit-message</code> and
           <code>file-version</code>.

           changeset : CHANGESET_ID : integer

           Retrieve only comments visible in the specified changeset. Can not be
           combined with the <code>commit</code> parameter.

           commit : COMMIT : integer or string

           Retrieve only comments visible in the specified commit, either in its
           commit message or in the commit's version of a file. Combine with the
           <code>location_type</code> parameter to select only one of those
           possibilities. Can not be combined with the <code>changeset</code>
           parameter."""

        critic = parameters.critic

        with_reply_parameter = parameters.getQueryParameter("with_reply")
        if with_reply_parameter:
            reply = api.reply.fetch(
                critic, reply_id=jsonapi.numeric_id(with_reply_parameter))
            return reply.comment

        review = jsonapi.deduce("v1/reviews", parameters)

        author_parameter = parameters.getQueryParameter("author")
        if author_parameter:
            user_id, name = jsonapi.id_or_name(author_parameter)
            author = api.user.fetch(critic, user_id=user_id, name=name)
        else:
            author = None

        comment_type_parameter = parameters.getQueryParameter("comment_type")
        if comment_type_parameter:
            if comment_type_parameter not in api.comment.Comment.TYPE_VALUES:
                raise jsonapi.UsageError("Invalid comment-type parameter: %r"
                                         % comment_type_parameter)
            comment_type = comment_type_parameter
        else:
            comment_type = None

        state_parameter = parameters.getQueryParameter("state")
        if state_parameter:
            if state_parameter not in api.comment.Issue.STATE_VALUES:
                raise jsonapi.UsageError(
                    "Invalid state parameter: %r" % state_parameter)
            state = state_parameter
        else:
            state = None

        location_type_parameter = parameters.getQueryParameter("location_type")
        if location_type_parameter:
            if location_type_parameter not in api.comment.Location.TYPE_VALUES:
                raise jsonapi.UsageError("Invalid location-type parameter: %r"
                                         % location_type_parameter)
            location_type = location_type_parameter
        else:
            location_type = None

        changeset = jsonapi.deduce("v1/changesets", parameters)
        commit = jsonapi.deduce("v1/commits", parameters)

        if changeset and commit:
            raise jsonapi.UsageError(
                "Incompatible parameters: changeset and commit")

        return api.comment.fetchAll(critic, review=review, author=author,
                                    comment_type=comment_type, state=state,
                                    location_type=location_type,
                                    changeset=changeset, commit=commit)

    @staticmethod
    def create(parameters, value, values, data):
        critic = parameters.critic
        user = parameters.context.get("users", critic.actual_user)
        path = parameters.subresource_path

        if value and path == ["replies"]:
            assert isinstance(value, api.comment.Comment)
            Comments.setAsContext(parameters, value)
            raise jsonapi.InternalRedirect("v1/replies")

        if value or values or path:
            raise jsonapi.UsageError("Invalid POST request")

        converted = jsonapi.convert(
            parameters,
            {
                "type": api.comment.Comment.TYPE_VALUES,
                "review!?": api.review.Review,
                "author?": api.user.User,
                "location?": {
                    # Note: "general" not included here; |location| should be
                    #       omitted instead.
                    "type": frozenset(["commit-message", "file-version"]),
                    "first_line": int,
                    "last_line": int,
                    "commit?": api.commit.Commit,
                    "file?": api.file.File,
                    "changeset?": api.changeset.Changeset,
                    "side?": frozenset(["old", "new"]),
                },
                "text": str
            },
            data)

        review = jsonapi.deduce("v1/reviews", parameters)

        if not review:
            if "review" not in converted:
                raise jsonapi.UsageError("No review specified")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise jsonapi.UsageError("Conflicting reviews specified")

        if "author" in converted:
            author = converted["author"]
        else:
            author = critic.actual_user

        if not converted["text"].strip():
            raise jsonapi.UsageError("Empty comment")

        if converted["type"] == "issue":
            expected_class = api.comment.Issue
        else:
            expected_class = api.comment.Note

        converted_location = converted.get("location")
        if converted_location:
            location_type = converted_location.pop("type")
            if location_type == "commit-message":
                required_fields = set(("first_line", "last_line", "commit"))
                optional_fields = set()
            else:
                required_fields = set(("first_line", "last_line", "file"))
                optional_fields = set(("commit", "changeset", "side"))
            accepted_fields = required_fields | optional_fields

            for required_field in required_fields:
                if required_field not in converted_location:
                    raise jsonapi.InputError(
                        "data.location.%s: missing attribute" % required_field)
            for actual_field in converted_location.keys():
                if actual_field not in accepted_fields:
                    raise jsonapi.InputError(
                        "data.location.%s: unexpected attribute" % actual_field)

            if location_type == "commit-message":
                max_line = len(
                    converted_location["commit"].message.splitlines())
            else:
                if "commit" in converted_location:
                    if "changeset" in converted_location:
                        raise jsonapi.InputError(
                            "data.location: only one of commit and changeset "
                            "can be specified")
                    changeset = None
                    side = None
                    commit = converted_location["commit"]
                elif "changeset" not in converted_location:
                    raise jsonapi.InputError(
                        "data.location: one of commit and changeset must be "
                        "specified")
                elif "side" not in converted_location:
                    raise jsonapi.InputError(
                        "data.location.side: missing attribute (required when "
                        "changeset is specified)")
                else:
                    changeset = converted_location["changeset"]
                    side = converted_location["side"]
                    commit = None

            first_line = converted_location["first_line"]
            last_line = converted_location["last_line"]

            if location_type == "commit-message":
                location = api.comment.CommitMessageLocation.make(
                    critic, first_line, last_line, converted_location["commit"])
            else:
                location = api.comment.FileVersionLocation.make(
                    critic, first_line, last_line, converted_location["file"],
                    changeset, side, commit)
        else:
            location = None

        result = []

        def collectComment(comment):
            assert isinstance(comment, expected_class), repr(comment)
            result.append(comment)

        with api.transaction.Transaction(critic) as transaction:
            transaction \
                .modifyReview(review) \
                .createComment(
                    comment_type=converted["type"],
                    author=author,
                    text=converted["text"],
                    location=location,
                    callback=collectComment)

        assert len(result) == 1, repr(result)
        return result[0], None

    @staticmethod
    def update(parameters, value, values, data):
        critic = parameters.critic
        path = parameters.subresource_path

        if value:
            comments = [value]
        else:
            comments = values

        if path:
            raise jsonapi.UsageError("Invalid PUT request")

        converted = jsonapi.convert(
            parameters,
            {
                "text": str
            },
            data)

        with api.transaction.Transaction(critic) as transaction:
            for comment in comments:
                transaction \
                    .modifyReview(comment.review) \
                    .modifyComment(comment) \
                    .setText(data["text"])

        return value, values

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic
        path = parameters.subresource_path

        if value:
            comments = [value]
        else:
            comments = values

        if path:
            raise jsonapi.UsageError("Invalid DELETE request")

        with api.transaction.Transaction(critic) as transaction:
            for comment in comments:
                transaction \
                    .modifyReview(comment.review) \
                    .modifyComment(comment) \
                    .delete()

    @staticmethod
    def deduce(parameters):
        comment = parameters.context.get("comments")
        comment_parameter = parameters.getQueryParameter("comment")
        if comment_parameter is not None:
            if comment is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: comment=%s" % comment_parameter)
            comment = api.comment.fetch(
                parameters.critic,
                comment_id=jsonapi.numeric_id(comment_parameter))
        return comment

    @staticmethod
    def setAsContext(parameters, comment):
        parameters.setContext(Comments.name, comment)
        return comment
