from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.users.models import User

from .forms import BrandForm, CategoryForm, ProductForm, UnitMeasureForm
from .models import Brand, Category, Product, UnitMeasure


class CatalogAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
	def test_func(self):
		return self.request.user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN}


class CatalogListView(CatalogAccessMixin, ListView):
	template_name = "products/catalog_list.html"
	context_object_name = "items"
	paginate_by = 20
	title = ""
	create_url_name = ""
	update_url_name = ""
	delete_url_name = ""

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update(
			title=self.title,
			create_url_name=self.create_url_name,
			update_url_name=self.update_url_name,
			delete_url_name=self.delete_url_name,
		)
		return context


class CatalogCreateView(CatalogAccessMixin, CreateView):
	template_name = "products/catalog_form.html"
	title = ""
	success_url_name = ""

	def get_success_url(self):
		return reverse_lazy(self.success_url_name)

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		messages.success(self.request, "Registro creado correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = self.title
		return context


class CatalogUpdateView(CatalogAccessMixin, UpdateView):
	template_name = "products/catalog_form.html"
	title = ""
	success_url_name = ""

	def get_success_url(self):
		return reverse_lazy(self.success_url_name)

	def form_valid(self, form):
		messages.success(self.request, "Registro actualizado correctamente.")
		return super().form_valid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["title"] = self.title
		return context


class CatalogDeleteView(CatalogAccessMixin, DeleteView):
	template_name = "products/confirm_delete.html"
	success_url_name = ""

	def get_success_url(self):
		return reverse_lazy(self.success_url_name)

	def form_valid(self, form):
		messages.success(self.request, "Registro eliminado correctamente.")
		return super().form_valid(form)


class CategoryListView(CatalogListView):
	model = Category
	title = "Categorías"
	create_url_name = "products:category-create"
	update_url_name = "products:category-update"
	delete_url_name = "products:category-delete"


class CategoryCreateView(CatalogCreateView):
	form_class = CategoryForm
	title = "Nueva categoría"
	success_url_name = "products:category-list"


class CategoryUpdateView(CatalogUpdateView):
	model = Category
	form_class = CategoryForm
	title = "Editar categoría"
	success_url_name = "products:category-list"


class CategoryDeleteView(CatalogDeleteView):
	model = Category
	success_url_name = "products:category-list"


class BrandListView(CatalogListView):
	model = Brand
	title = "Marcas"
	create_url_name = "products:brand-create"
	update_url_name = "products:brand-update"
	delete_url_name = "products:brand-delete"


class BrandCreateView(CatalogCreateView):
	form_class = BrandForm
	title = "Nueva marca"
	success_url_name = "products:brand-list"


class BrandUpdateView(CatalogUpdateView):
	model = Brand
	form_class = BrandForm
	title = "Editar marca"
	success_url_name = "products:brand-list"


class BrandDeleteView(CatalogDeleteView):
	model = Brand
	success_url_name = "products:brand-list"


class UnitMeasureListView(CatalogListView):
	model = UnitMeasure
	title = "Unidades de medida"
	create_url_name = "products:unit-measure-create"
	update_url_name = "products:unit-measure-update"
	delete_url_name = "products:unit-measure-delete"


class UnitMeasureCreateView(CatalogCreateView):
	form_class = UnitMeasureForm
	title = "Nueva unidad de medida"
	success_url_name = "products:unit-measure-list"


class UnitMeasureUpdateView(CatalogUpdateView):
	model = UnitMeasure
	form_class = UnitMeasureForm
	title = "Editar unidad de medida"
	success_url_name = "products:unit-measure-list"


class UnitMeasureDeleteView(CatalogDeleteView):
	model = UnitMeasure
	success_url_name = "products:unit-measure-list"


class ProductListView(CatalogAccessMixin, ListView):
	model = Product
	template_name = "products/list.html"
	context_object_name = "products"
	paginate_by = 20
	queryset = Product.objects.select_related("category", "brand", "unit_measure")


class ProductCreateView(CatalogCreateView):
	form_class = ProductForm
	template_name = "products/form.html"
	title = "Nuevo producto"
	success_url_name = "products:list"


class ProductUpdateView(CatalogUpdateView):
	model = Product
	form_class = ProductForm
	template_name = "products/form.html"
	title = "Editar producto"
	success_url_name = "products:list"


class ProductDeleteView(CatalogDeleteView):
	model = Product
	success_url_name = "products:list"

