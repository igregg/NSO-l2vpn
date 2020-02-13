## NSO-l2vpn
YANG and Python template for MPLS L2VPN provisioning.

## Requirement

- NSO Version: \> 5.1.x
- NED
  - cisco-ios-cli-6.39
  - cisco-iosxr-cli-7.17
  
## Installation
```
git clone https://github.com/igregg/NSO-l2vpn.git l2vpn
```


## Re-complie YANG

```
cd src
make clean all
```

don't forget to reload the packages in NCS.
