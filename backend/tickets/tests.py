
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from tickets.models import Ticket


User = get_user_model()


class TicketAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='customer',
            password='test-password',
        )
        self.other_user = User.objects.create_user(
            username='other-customer',
            password='test-password',
        )
        self.staff = User.objects.create_user(
            username='staff',
            password='test-password',
            is_staff=True,
        )
        self.list_url = reverse('ticket-list')
        self.ticket = Ticket.objects.create(
            title='Existing ticket',
            description='Existing description',
            category=Ticket.Category.TECHNICAL,
            priority=Ticket.Priority.HIGH,
            created_by=self.user,
        )
        self.other_ticket = Ticket.objects.create(
            title='Other ticket',
            description='Other description',
            created_by=self.other_user,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_unauthenticated_access_is_rejected(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_create_ticket_with_authenticated_owner(self):
        self.authenticate(self.user)

        response = self.client.post(self.list_url, {
            'title': 'New ticket',
            'description': 'A new customer issue',
            'category': Ticket.Category.BILLING,
            'priority': Ticket.Priority.URGENT,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.user.pk)
        self.assertEqual(response.data['status'], Ticket.Status.OPEN)

    def test_user_listing_contains_only_own_tickets(self):
        self.authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.ticket.pk)

    def test_ticket_listing_supports_custom_page_size(self):
        self.authenticate(self.user)

        for index in range(11):
            Ticket.objects.create(
                title=f'Ticket {index}',
                description='Pagination test',
                created_by=self.user,
            )

        response = self.client.get(
            self.list_url,
            {'page_size': 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 12)
        self.assertEqual(len(response.data['results']), 2)
        self.assertIsNotNone(response.data['next'])

    def test_ticket_listing_enforces_maximum_page_size(self):
        self.authenticate(self.user)

        for index in range(101):
            Ticket.objects.create(
                title=f'Pagination ticket {index}',
                description='Maximum page size test',
                created_by=self.user,
            )

        response = self.client.get(
            self.list_url,
            {'page_size': 150},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 102)
        self.assertEqual(len(response.data['results']), 100)
        self.assertIsNotNone(response.data['next'])

    def test_staff_listing_contains_all_tickets(self):
        self.authenticate(self.staff)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_user_can_retrieve_own_ticket(self):
        self.authenticate(self.user)

        response = self.client.get(
            reverse('ticket-detail', args=[self.ticket.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.ticket.pk)

    def test_user_cannot_retrieve_another_users_ticket(self):
        self.authenticate(self.user)

        response = self.client.get(
            reverse('ticket-detail', args=[self.other_ticket.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_update_own_ticket(self):
        self.authenticate(self.user)

        response = self.client.patch(
            reverse('ticket-detail', args=[self.ticket.pk]),
            {'status': Ticket.Status.IN_PROGRESS},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.IN_PROGRESS)

    def test_user_cannot_assign_ticket_to_another_user(self):
        self.authenticate(self.user)

        response = self.client.patch(
            reverse('ticket-detail', args=[self.ticket.pk]),
            {'assigned_to': self.other_user.pk},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('assigned_to', response.data)

    def test_user_can_delete_own_ticket(self):
        self.authenticate(self.user)

        response = self.client.delete(
            reverse('ticket-detail', args=[self.ticket.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Ticket.objects.filter(pk=self.ticket.pk).exists())

    def test_invalid_input_is_rejected(self):
        self.authenticate(self.user)

        response = self.client.post(self.list_url, {
            'title': '',
            'description': 'Invalid ticket',
            'category': 'INVALID',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)
        self.assertIn('category', response.data)

    def test_whitespace_only_ticket_content_is_rejected(self):
        self.authenticate(self.user)

        response = self.client.post(self.list_url, {
            'title': '   ',
            'description': '\n\t',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)
        self.assertIn('description', response.data)

    def test_ticket_content_is_trimmed_before_persistence(self):
        self.authenticate(self.user)

        response = self.client.post(self.list_url, {
            'title': '  Login issue  ',
            'description': '  Cannot sign in.  ',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket = Ticket.objects.get(pk=response.data['id'])
        self.assertEqual(ticket.title, 'Login issue')
        self.assertEqual(ticket.description, 'Cannot sign in.')

    def test_filtering_by_status_priority_and_category(self):
        self.authenticate(self.staff)

        response = self.client.get(self.list_url, {
            'status': Ticket.Status.OPEN,
            'priority': Ticket.Priority.HIGH,
            'category': Ticket.Category.TECHNICAL,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.ticket.pk)

    def test_invalid_filter_is_rejected(self):
        self.authenticate(self.staff)

        response = self.client.get(self.list_url, {'status': 'UNKNOWN'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
    def test_staff_can_assign_ticket_to_another_user(self):
        self.authenticate(self.staff)

        response = self.client.patch(
            reverse('ticket-detail', args=[self.ticket.pk]),
            {'assigned_to': self.other_user.pk},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to, self.other_user)
    def test_ticket_listing_uses_id_to_break_creation_timestamp_ties(self):
        self.authenticate(self.staff)

        Ticket.objects.filter(
            pk__in=[self.ticket.pk, self.other_ticket.pk]
        ).update(created_at=self.ticket.created_at)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ticket_ids = [item['id'] for item in response.data['results']]
        self.assertEqual(ticket_ids, sorted(ticket_ids, reverse=True))
        
    def test_customer_cannot_assign_ticket_to_themselves(self):
        self.authenticate(self.user)

        response = self.client.patch(
            reverse('ticket-detail', args=[self.ticket.pk]),
            {'assigned_to': self.user.pk},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('assigned_to', response.data)
    def test_new_ticket_uses_default_field_values(self):
        self.authenticate(self.user)

        response = self.client.post(
            self.list_url,
            {
                'title': 'Default values test',
                'description': 'Checking ticket defaults',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], Ticket.Status.OPEN)
        self.assertEqual(response.data['priority'], Ticket.Priority.MEDIUM)
        self.assertEqual(response.data['category'], Ticket.Category.GENERAL)
    def test_ticket_updated_at_changes_after_update(self):
        self.authenticate(self.user)
        original_updated_at = self.ticket.updated_at

        response = self.client.patch(
            reverse('ticket-detail', args=[self.ticket.pk]),
            {'title': 'Updated ticket title'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.ticket.refresh_from_db()
        self.assertGreater(self.ticket.updated_at, original_updated_at)
    def test_user_cannot_delete_another_users_ticket(self):
        self.authenticate(self.user)

        response = self.client.delete(
            reverse('ticket-detail', args=[self.other_ticket.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Ticket.objects.filter(pk=self.other_ticket.pk).exists()
        )
    def test_staff_can_update_another_users_ticket(self):
        self.authenticate(self.staff)

        response = self.client.patch(
            reverse('ticket-detail', args=[self.other_ticket.pk]),
            {'status': Ticket.Status.IN_PROGRESS},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.other_ticket.refresh_from_db()
        self.assertEqual(
            self.other_ticket.status,
            Ticket.Status.IN_PROGRESS,
        )
    def test_ticket_filtering_by_priority(self):
        self.authenticate(self.staff)

        response = self.client.get(
            self.list_url,
            {'priority': Ticket.Priority.HIGH},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            self.ticket.pk,
        )  
    def test_ticket_filtering_by_category(self):
        self.authenticate(self.staff)

        response = self.client.get(
            self.list_url,
            {'category': Ticket.Category.TECHNICAL},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['id'],
            self.ticket.pk,
        )  