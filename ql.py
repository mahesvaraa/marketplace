import asyncio

import aiohttp


async def introspect_graphql_schema(endpoint: str):
    query = """
    {
      __schema {
        types {
          name
          kind
          fields {
            name
            type {
              name
              kind
            }
            args {
              name
              type {
                name
                kind
              }
            }
          }
        }
      }
    }
    """

    headers = {
        'content-type': 'application/json',
                        'Authorization': f"ubi_v1 t=ewogICJ2ZXIiOiAiMSIsCiAgImFpZCI6ICI5OWY1OGIzMi0xZmU2LTRlZmMtOTQyZi0xNDNjZTc3OWZhYzIiLAogICJlbnYiOiAiUHJvZCIsCiAgInNpZCI6ICI3NGExMGM5NC04YjczLTQwMTctOGMwZS1iNWI5MjdlMmRmZTIiLAogICJ0eXAiOiAiSldFIiwKICAiZW5jIjogIkExMjhDQkMiLAogICJpdiI6ICJTVEdtbWhNSEJiS3ZYM0pDLVJkbnVBIiwKICAiaW50IjogIkhTMjU2IiwKICAia2lkIjogIjdiYTRjYzQwLTYwODItNDBjNS1iOWFkLTA0ZDE3NWMxMDY0YSIKfQ.solSWsg4L4SRzTPMWRfFKlfdSPJHeKXFzjtpfHd3EnZ44B2fEv60i1iFOs9d7XBwl8X4b1zlyu89dihcwECdBqECTFsYfajdxObrDfEPg1TX4EJxFVlYOUQZJwcsoMPDQom5KRrRDyfgYMsvkU7pe_aodEVw0TJ31AwGv0hOihvryU5SunN9wWaeM5fS3KnXm8k_JYZywSIFrp_1_qqJvB9mXiEGK-PJSLsjYmGmsELMBtgHfIgUf9k653D1KQaK0nTZg4OjRlqKVhBEbnupWQMx3TB53UBKiH5xZT2fqRj3S8z8qXpuqXNT8iX020PgYmRp3iCsd7T0t7uCYMFQfzeYVIVYnpsnooH3natU2Y9vBi_Ug7mHsCSWwbr3O6CVCn2I4gS6SwBY2kqnPCXCw6Pi8qzmWlS-eTDzR5HJujIpStRwIs2H98LDqsnfJFLEVTTjJBUOAqqdzvDtoAcKGHhbxdCjjcJp7bkrUn1yoq2aj6mcttzBbPHYr2eHWCB8K044fxYJovaI1mic2vyuw63Pe-4aevzr8ox9O_gMd9j2WPqEZwXzNtSOOMJQWtMVJfl-AbaBERj--ohRuYalVlsXGEegx3FoCBU7wgJZ_7jUnpFnFoKbxotxI-nMb4VOg6pGN7hwms8h_n-ZxAATxeGhvVjE9htnbkq1q1M8OvWu6XsNV7AEqNnZrCXaJGGelSswJYF4cu09MEctDrhE_g43Ub9nXkr84WcamkHuquX_dYj59QzhR6XdkHuekTWAhosvYPmOku0Q1h20TIzFJw95aygxT512I8D1sAfRf-pYxdJQ1C91BTaLrxFx6TNaWq7NNosI7eqXg8B1WH2MntsOdOocP9N43lis0uakwWW4FnaaXRJ7SgrYIYthpAs472wv4y18M5tX8SS9YhT0Baol_XVDDRU_3VVECUjYRnwIWM974bma-1zJEWDoITdCvehsh6it6yC5kcW4B1MjoHbKbvNxCO-VCfachbiI0qK6rr_Vn6qxno2FCp1mSXfN1Hn2YETpHTlcTUj3GUHiXpi7m1Xvv7RBJIXWpUTsOiyV9jLf5FPgJRiTXkdMu2-giJSiEbMqxKhRdl21VJ29ZdZRoll_vgGxAHynpsl-BINObeqAg9axl2kyHoNHHrDR0fOhFx8egQyWyRP1IqnFM6hufUCxzoYEV1uFnNTpAzdAK_yLwndZvQz_8BgBfV60rk2LOoEk5ZguneN9AlBCb7wCrYzrQAwXc26NTQSA0qMGjEHGBY1jsoRhEnRSk8J3dgHmEX96vJhmHk-XQ_H-452X23VJYND0t7a21S0_s5yj_gyhm981itFXOuiTmAwE1anrVUrTtmHs2Rr1oi7nxNJyF_EJFhVpzSrHvAvJcMv9pWBFISUSTllML9D0UEP3CWrkZiHe7E53Jjx_L-Ev41p4bmr_y_uY8mZQU5ZUURLm3MQE52xP2cOiIzzRWGl2D5nq0FISEVFnYBaVaf3lM5HDq6_Ij-aMB-xSZ_R_AQ1gfOsPfqfwfIs2LT_eZeGTbfHTHNvxvPMyreH8CwF_BtmvIGd7Mmh8LAIMUXH2N7-FFlEsOdIMjs0W8jY5gRKtoO3rlDTfnTpleX7dS3ynz2ivDfQ8wl-Qt3OcAExqZL5mvV82EXon4vrDyrO-DD0v6Nw_FrOxY0N66iz_REr2H5L6CzYyvWje8m8MJ62_CD2bCwATe1RjIK50lMBebfYZXNeKvam7fvpl_L_d2OTmR-ynQbMvu-7rV5leogDEXhv69vWsuCFZMCH3ndhzK0BWFF2zoLQCM4mCDZQnzTVLXAl1k90hCSMiuyZe0l0DdORfvuMq5Pd6nvGoL0sOGwH0IQ3TOKBTfcNzsgmaygISngnF-QfRwa8hdvIUSKt5cUkzLxwt22Hz9ANv7xbYH4qWy6yxAkyMKmm5uEafjUz2qaV_pYaiOQJmp6ES77YbH1NdW4x8zye1SHt9Lxo7vnfU8WFavr078jer_qJyhwrYACiM-Ekz2YDhGQ1a3gkW_FoY4ameKRYH5lxlJV91dgWLKxG-HF7BQRH4-3oJnwWcZRzaozMOezEPPUdw9kc6ZuZtzCwF56qtLGGU0XZRqY_zIiIcbQkCBYcOil7kOdQhrDRdYmBZXLl0KhAMPs5vRxklN7_g5UyjvXNRpYJ2WZ4J9ENV7vgbi5pmnF-7YiHB7VlBpfoFJzohMz8T0Fm7kMHOBWKEuzGglvoaoGJ8rj9ArYExnAdL_ObKh50cIB6cF-RrwrL-uTprnf0F8v8CRqXLtF9ryCIguiR6CzMOWTjMGry4Xg2U1bkTeZ-fHW10ZxaKmpzO2ZF6WIRdJzhcPi3x_XccW6rZK6cIy6Ns2eMPgJWTEVuzcR_30BhTGL4j7Xe5lqMZ5AYdNAKcarICltHNM9tAHqas59shnhxS86fGDSO1OUfsNzPWB7IJDRivivB4JsKJO-Lpue7cvBbRVajCdoJ5OWh1i87LHP-hcjSW0fFuFB74wdQc0z3CvP5LvMayRkgrWfyrUPk8uKclKTyV5pdGAsP1xCyI4ZITT1Y-9PHHVCZmF7SfBW3oI17NPdk6m5-kkodx_ue3WVWJ3DKYquHEdxTMC3qLggahlQFyvM3WWJOYk6nuofD4JTF_sw5qD9ekRb44K3VPn9xD4UzyPCkBLqLHhPhK_ZRn8iDoaJTCunF7QG1xvKQbjmfrQW4O2mmUSL5NJkCUprV7smCjoPgJbDnyqEQDdQPzf__omjW6bpEzwBQsRNt08MICIk9GJkwwiTRil6CmkmQMMm32GDGMDbNW6b-j5rTVlikoUPb1BM4mN2LOoipLsd9x-9BFGOTLcdusbW5bEXr-d03bkG3CB7JpYYo5SlYF29D4bAeb_QFO8wj1xpU-_kU_yG1i804YHtzpOmAyoZYKI3au1k4OuPQkhKPrvsbqMf-K7DBjeffxnN5swAkmcMf36wFizVV7uKNZr8nuxrHHiY82bcMHneWIIPenhZSjp1MSmcnFSs7p4k5CxDHL7wmUn16hvue34XSKT2g-19jC0Fg6nMPZeIdgOMx5uFAQ8uYPAUz2jJI3fSvGwMQhVRHpVFBTyUtegrboPQHy8_1aAo0Dyd0s06fY3AWd4ergbJIVeHttZ3RdVEr6kjg-XDK1Gs-IaCt9wQ1w_A8OcyoKxZ_spfS3v6s9CEkuMe9GcyYzsr0nI6N4hhWhBDGcU0BejxJ3VMr6yik4LSC0mx4Dd9Rbhu7hVg-rx16A0ZYFFc0VAjWrO8EGwKkJG0qjLMfFdfmrSgYUvUpfO0s27RngvK_OIbGx0myLSi-XF8WUNm8BO-6MLp7tiKS7N8GUychjE8R3lafGht4msPPSy_-qZJDGDXh5SPj2cSuA9K3x9rla7tPJp4pB3HZdMzIQu40vuf4BevfCcr1iByd-djZLkkThrIXTN1_BtaNqdus0CytS-w9rAZ2t1rdUuNwtDemBC3gu57z8ZgQTs4I5JjdjQjJbsCqcyA31rBLLEbY7k8v6PVnti12SCZyCeV2SeKTVuF6qgFQrZUxO0QCKm6Xa4685RFTQCQyGByjNo9kZMHpB.Y7_osWlDi2anm1hlJ7KTzGAhVZLDxjKf94IWqrxQYBY",
                        'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
                        'Ubi-SessionId': '88c422ca-73c4-437f-92e3-25f03b08cc2b',
                        'User-Agent': 'UbiServices_SDK_2020.Release.58_PC64_ansi_static',
                        'Ubi-Localecode': 'ru-RU',
                        'Ubi-Countryid': 'RU'
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, json={"query": query}, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                print(f"Failed to fetch schema, status: {response.status}, message: {await response.text()}")
                return None


# Пример использования
async def main():
    endpoint = "https://public-ubiservices.ubi.com/v1/profiles/me/uplay/graphql"  # Замените на ваш GraphQL endpoint
    schema = await introspect_graphql_schema(endpoint)
    if schema:
        print(schema)

asyncio.run(main())