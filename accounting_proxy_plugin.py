from urlparse import urlparse
import requests

from django.conf import settings

from wstore.asset_manager.resource_plugins.plugin import Plugin
from wstore.asset_manager.resource_plugins.plugin_error import PluginError


class AccountingProxyPlugin(Plugin):

    def record_type(self, unit):
        return {
            'call': 'callusage',
            'megabyte': 'datausage' 
        }[unit]

    def on_post_product_spec_validation(self, provider, asset):
        # Get the apiKey for accounting notifications
        try:
            acc_proxy_url = urlparse(asset.get_url()).scheme + '://' + urlparse(asset.get_url()).netloc
            authorize_url = settings.AUTHORIZE_SERVICE

            resp = requests.post(authorize_url, json={'url': acc_proxy_url})

            if resp.status_code != 201:
                raise PluginError('Error getting the api_key')

            else:
                # Check the url and send the apiKey
                api_key = resp.json()['apiKey']

                url = acc_proxy_url + '/accounting_proxy/urls'
                headers = {'X-API-KEY': api_key,
                           'authorization': 'bearer ' + provider.userprofile.access_token}
                payload = {'url': asset.get_url()}

                resp = requests.post(url, headers=headers, json=payload)

                if resp.status_code != 200:
                    raise PluginError('Invalid asset url')

                else:
                    # Commit the apiKey received
                    authorize_url = settings.AUTHORIZE_SERVICE + '/' + api_key + '/commit'

                    resp = requests.post(authorize_url)

                    if resp.status_code != 200:
                        raise PluginError('Error committing the api_key')

        except Exception as e:
            # Remove the asset to avoid an inconsistent state in  the database
            asset.delete()
            raise e

    def on_post_product_offering_validation(self, asset, product_offering):
        # Check supported accounting units
        url = urlparse(asset.get_url()).scheme + '://' + urlparse(asset.get_url()).netloc + '/accounting_proxy/units'

        resp = requests.get(url)

        if resp.status_code != 200:
            raise PluginError('Error checking the supported accounting units')
        else:
            units = resp.json()['units']
            found = False

            for price_model in product_offering['productOfferingPrice']:

                if price_model['priceType'] == 'usage' and price_model['unitOfMeasure'] not in units:
                    raise PluginError('Unsupported accounting unit ' + price_model['unit'] + '. Supported units are: ' + units)
                if price_model['priceType'] == 'usage' and price_model['unitOfMeasure'] in units:
                    found = True

            if not found:
                raise PluginError('No "usage" price type in the product_offering')

    def on_product_acquisition(self, asset, contract, order):
        # Send new buy notification to the accounting proxy
        url = urlparse(asset.get_url()).scheme + '://' + urlparse(asset.get_url()).netloc + '/accounting_proxy/buys'

        if 'pay_per_use' in contract.pricing_model:

            count = 0
            for price_model in contract.pricing_model['pay_per_use']:
                if 'unit' in price_model:
                    unit = price_model['unit']
                    count += 1

            if count != 1:
                raise PluginError('Wrong number of pricing components. Only one pricing component is supported')
            else:

                payload = { 
                    'productId': unicode(contract.product_id),
                    'orderId': unicode(order.order_id),
                    'customer': order.customer.username,
                    'productSpecification': {
                        'url': asset.get_url(),
                        'unit': unit,
                        'recordType': self.record_type(unit)
                    }
                }

                resp = requests.post(url, json=payload)

                if resp.status_code != 201:
                    raise PluginError('Error notifying the product acquisition to the accounting proxy')
        else: 
            raise PluginError('Contract must have a "pay per use" in the pricing_model')
