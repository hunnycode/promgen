# Copyright (c) 2017 LINE Corporation
# These sources are released under the terms of the MIT license: see LICENSE

import json
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from promgen import models, tests
from promgen.notification.slack import NotificationSlack

TEST_SETTINGS = tests.Data('examples', 'promgen.yml').yaml()
TEST_ALERT = tests.Data('examples', 'alertmanager.json').raw()


class SlackTest(tests.PromgenTest):
    TestHook1 = 'https://hooks.slack.com/services/XXXXXXXXX/XXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXX'
    TestHook2 = 'https://hooks.slack.com/services/YYYYYYYYY/YYYYYYYYY/YYYYYYYYYYYYYYYYYYYYYYYY'

    @mock.patch('django.dispatch.dispatcher.Signal.send')
    def setUp(self, mock_signal):
        self.shard = models.Shard.objects.create(name='test.shard')
        self.service = models.Service.objects.create(name='test.service')
        self.project = models.Project.objects.create(name='test.project', service=self.service, shard=self.shard)

        self.sender = models.Sender.objects.create(
            obj=self.project,
            sender=NotificationSlack.__module__,
            value=self.TestHook1,
        )

        self.service2 = models.Service.objects.create(name='other.service')
        self.sender2 = models.Sender.objects.create(
            obj=self.service2,
            sender=NotificationSlack.__module__,
            value=self.TestHook2,
        )

    @override_settings(PROMGEN=TEST_SETTINGS)
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @mock.patch('promgen.util.post')
    def test_slack(self, mock_post):
        self.client.post(reverse('alert'),
            data=TEST_ALERT,
            content_type='application/json'
        )

        # Swap the status to test our resolved alert
        SAMPLE = tests.Data('examples', 'alertmanager.json').json()
        SAMPLE['status'] = 'resolved'
        SAMPLE['commonLabels']['service'] = self.service2.name
        SAMPLE['commonLabels'].pop('project')
        self.client.post(reverse('alert'),
            data=json.dumps(SAMPLE),
            content_type='application/json'
        )

        _MESSAGE = tests.Data('notification', 'slack.body.txt').raw().strip()
        _RESOLVED = tests.Data('notification', 'slack.resolved.txt').raw().strip()

        mock_post.assert_has_calls([
            mock.call(
                self.TestHook1,
                json={'text': _MESSAGE.format(service=self.service, project=self.project)},
            ),
            mock.call(
                self.TestHook2,
                json={'text': _RESOLVED},
            ),
        ], any_order=True)
