"""An XBlock for in-course reverification. """

import logging

from django.template import Context, Template

import pkg_resources
from xblock.core import XBlock
from xblock.fields import Scope, String, Boolean, Integer, DateTime
from xblock.fragment import Fragment


log = logging.getLogger(__name__)
CHECKPOINT_NAME = "Assessment 1"


@XBlock.wants("reverification")
class ReverificationBlock(XBlock):
    """An XBlock for in-course reverification. """

    # Fields
    display_name = String(
        scope=Scope.settings,
        default='Re-Verification Checkpoint',
        help="This name appears in the horizontal navigation at the top of "
             "the page."
    )

    attempts = Integer(
        display_name="Verification Attempts",
        default=0,
        scope=Scope.settings,
        help="This is the number of attempts that students are permitted to "
             "get a valid re-verification."
    )

    related_assessment = String(
        display_name="Related Assessment",
        scope=Scope.content,
        default=CHECKPOINT_NAME,
        help="This name will allow you to distinguish distinct checkpoints "
             "that show up in the reporting about student verification status."
    )

    is_configured = Boolean(
        scope=Scope.content,
        default=False,
        help="Reverification XBlock is configured or not."
    )

    due = DateTime(
        display_name="Related Assessment due date",
        scope=Scope.settings,
        default=None,
        help="ISO-8601 formatted string representing the due date of this related assessment."
    )

    @property
    def course_id(self):
        """Retrieve the course ID.

        Returns:
            CourseKey

        """
        # Note: this relies on an unsupported API (xmodule_runtime),
        # which is currently the only way to retrieve the course ID
        # from the LMS.  If the course ID is not available,
        # we use a default course ID for testing (usually in workbench).
        return (
            unicode(self.xmodule_runtime.course_id)
            if hasattr(self, "xmodule_runtime")
            else "edX/Enchantment_101/April_1"
        )

    @property
    def in_studio_preview(self):
        """
        Check whether we are in Studio preview mode.

        Returns:
            bool

        """
        # When we're running in Studio Preview mode, the XBlock won't provide us with a user ID.
        # (Note that `self.xmodule_runtime` will still provide an anonymous
        # student ID, so we can't rely on that)
        return self.scope_ids.user_id is None

    @property
    def is_released(self):
        """
        Check if a xblock has been released.

        Returns:
            bool
        """
        # By default, assume that we're published, in case the runtime doesn't support publish date.
        return self.runtime.modulestore.has_published_version(self) if hasattr(self.runtime, 'modulestore') else True

    def student_view(self, context=None):
        """Student view to render the re-verification link

        This will render the url to display in lms along with marketing text.

        """
        # Assume that if service is not available then it is
        # in studio_preview because service are defined in LMS
        if not self.runtime.service(self, "reverification"):
            return self.get_studio_preview()

        course_id = self.course_id
        item_id = unicode(self.scope_ids.usage_id)
        related_assessment = self.related_assessment
        user_id = unicode(self.scope_ids.user_id)
        fragment = Fragment()

        verification_status = self.runtime.service(self, "reverification").get_status(
            user_id=user_id,
            course_id=course_id,
            related_assessment=related_assessment
        )

        if verification_status:
            # TODO: What message will be displayed to user if it is already has any status?
            fragment.add_content(unicode(verification_status))
        else:
            reverification_link = self.runtime.service(self, "reverification").start_verification(
                course_id=course_id,
                related_assessment=related_assessment,
                item_id=item_id
            )
            html = self._render_template(
                "static/html/reverification.html",
                {
                    'reverification_link': reverification_link,
                }
            )
            fragment.add_content(html)
            fragment.add_javascript(self._resource("static/js/skip_reverification.js"))
            fragment.initialize_js('SkipReverifcation')

        fragment.add_css(self._resource("static/reverification.min.css"))
        return fragment

    def studio_view(self, context):
        """
        Create a fragment used to display the edit view in the Studio.
        """
        try:
            cls = type(self)

            def none_to_empty(data):
                """
                Return empty string if data is None else return data.
                """
                return data if data is not None else ''

            edit_fields = (
                (field, none_to_empty(getattr(self, field.name)), validator)
                for field, validator in (
                    (cls.related_assessment, 'string'),
                    (cls.attempts, 'number'))
            )

            context = {
                'fields': edit_fields
            }
            fragment = Fragment()
            fragment.add_content(
                self._render_template(
                    'static/html/checkpoint_edit.html',
                    context
                )
            )
            fragment.add_javascript(self._resource("static/js/checkpoint_edit.js"))
            fragment.initialize_js('CheckpointEditBlock')
            return fragment
        except:  # pragma: NO COVER
            log.error("Error creating fragment for studio edit view", exc_info=True)
            raise

    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        Called when submitting the form in Studio.
        """
        self.related_assessment = data.get('related_assessment')
        self.attempts = data.get('attempts')
        self.is_configured = True

        return {'result': 'success'}

    @staticmethod
    def workbench_scenarios():
        return [
            (
                "Reverification Block",
                ReverificationBlock._resource("static/xml/reverification_block_example.xml")
            ),
        ]

    @XBlock.json_handler
    def skip_verification(self, data, suffix=''):
        """
        Called when submitting the form in Studio for skipping verification.
        """
        checkpoint = data.get("checkpoint")
        user_id = data.get("user_id")
        course_id = data.get("course_id")
        self.runtime.service(self, "reverification").skip_verification(
            checkpoint,
            user_id,
            course_id
        )

        return {'result': 'success'}

    def get_studio_preview(self):
        """ Return rendered studio view """
        context = {
            "is_configured": self.is_configured,
            "view_container_link": "/container/" + unicode(self.scope_ids.usage_id)
        }

        fragment = Fragment()
        fragment.add_content(
            self._render_template(
                'static/html/studio_preview.html',
                context
            )
        )

        return fragment

    @staticmethod
    def _resource(path):
        """
        Handy helper for getting resources from our kit.
        """
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    @staticmethod
    def _render_template(template_path, context):
        """
        Evaluate a template by resource path, applying the provided context.
        """
        template_str = ReverificationBlock._resource(template_path)
        template = Template(template_str)
        return template.render(Context(context))
