from decimal import Decimal

from django.test import TestCase

from apps.branches.models import Branch
from apps.inventory.models import Stock
from apps.products.models import Product
from apps.transfers.models import Transfer, TransferItem
from apps.transfers.services import receive_transfer, send_transfer
from apps.users.models import User


class TransferServiceTests(TestCase):
    def setUp(self):
        self.origin = Branch.objects.create(name="Central", code="CENTRAL")
        self.destination = Branch.objects.create(name="Norte", code="NORTE")
        self.product = Product.objects.create(name="Coca Cola", sku="COCA-600")
        self.user = User.objects.create_user(
            username="admin",
            password="test-password",
            branch=self.origin,
            role=User.ROLE_ADMIN,
        )
        Stock.objects.create(product=self.product, branch=self.origin, quantity=Decimal("20"))

    def test_send_and_receive_transfer_moves_stock_between_branches(self):
        transfer = Transfer.objects.create(
            origin_branch=self.origin,
            destination_branch=self.destination,
            created_by=self.user,
        )
        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            requested_quantity=Decimal("12"),
        )

        send_transfer(transfer, self.user)
        receive_transfer(transfer, self.user, {})

        transfer.refresh_from_db()
        self.assertEqual(transfer.status, Transfer.STATUS_RECEIVED)
        self.assertIsNotNone(transfer.outgoing_movement)
        self.assertIsNotNone(transfer.incoming_movement)
        self.assertEqual(Stock.objects.get(product=self.product, branch=self.origin).quantity, Decimal("8"))
        self.assertEqual(Stock.objects.get(product=self.product, branch=self.destination).quantity, Decimal("12"))