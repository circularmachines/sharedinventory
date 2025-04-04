app.bsky.notification.list_notifications
class atproto_client.models.app.bsky.notification.list_notifications.Notification
Bases: ModelBase

Definition model for app.bsky.notification.listNotifications.

field author: models.AppBskyActorDefs.ProfileView [Required]
Author.

field cid: str [Required]
Cid.

Constraints:
func = Validated by: string_formats.validate_cid()
atproto_client.models.string_formats.validate_cid(v: str, _: ValidationInfo) → str
 (only when strict_string_format=True)

json_schema_input_type = PydanticUndefined

field indexed_at: str [Required]
Indexed at.

Constraints:
func = Validated by: string_formats.validate_datetime() (only when strict_string_format=True)

json_schema_input_type = PydanticUndefined

field is_read: bool [Required]
Is read.

field labels: List[models.ComAtprotoLabelDefs.Label] | None = None
Labels.

field py_type: Literal['app.bsky.notification.listNotifications#notification'] = 'app.bsky.notification.listNotifications#notification'
field reason: Literal['like'] | Literal['repost'] | Literal['follow'] | Literal['mention'] | Literal['reply'] | Literal['quote'] | Literal['starterpack-joined'] | str [Required]
Expected values are ‘like’, ‘repost’, ‘follow’, ‘mention’, ‘reply’, ‘quote’, and ‘starterpack-joined’.

field reason_subject: str | None = None
Reason subject.

field record: UnknownType [Required]
Record.

field uri: str [Required]
Uri.

Constraints:
func = Validated by: string_formats.validate_at_uri() (only when strict_string_format=True)

json_schema_input_type = PydanticUndefined

class atproto_client.models.app.bsky.notification.list_notifications.Params
Bases: ParamsModelBase

Parameters model for app.bsky.notification.listNotifications.

field cursor: str | None = None
Cursor.

field limit: int | None = 50
Limit.

Constraints:
ge = 1

le = 100

field priority: bool | None = None
Priority.

field reasons: List[str] | None = None
field seen_at: str | None = None
Seen at.

class atproto_client.models.app.bsky.notification.list_notifications.ParamsDict(*args, **kwargs)
Bases: dict

cursor: typing_extensions.NotRequired[str | None]
Cursor.

limit: typing_extensions.NotRequired[int | None]
Limit.

priority: typing_extensions.NotRequired[bool | None]
Priority.

reasons: typing_extensions.NotRequired[List[str] | None]
Notification reasons to include in response. A reason that matches the reason property of #notification.

seen_at: typing_extensions.NotRequired[str[str] | None]
Seen at.

class atproto_client.models.app.bsky.notification.list_notifications.Response
Bases: ResponseModelBase

Output data model for app.bsky.notification.listNotifications.

field cursor: str | None = None
Cursor.

field notifications: List[models.AppBskyNotificationListNotifications.Notification] [Required]
Notifications.

field priority: bool | None = None
Priority.

field seen_at: str | None = None
Seen at.